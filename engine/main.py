"""
Fraud detection engine API.

Jobs:
1. POST /transactions  -> receives a transaction from the generator,
   scores it, updates the fraud-ring graph, broadcasts the result to
   all connected dashboards, and fires an n8n webhook if flagged.
2. WS   /ws             -> dashboard clients connect here to receive a
   live feed of scored transactions + graph updates.
3. GET  /graph          -> full current graph snapshot.
4. GET  /stats          -> running totals for the impact-metrics panel.
5. POST /alertflag      -> manually (re)fire the n8n webhook for a given
   flagged transaction — useful for testing the webhook without waiting
   on a live anomaly, or for an analyst to re-send an alert.

Run with:
    uvicorn main:app --reload --port 8000
"""

import time
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import json
import os
import logging
import httpx

from schemas import Transaction, RiskResult, FeedbackPayload, AlertFlagPayload, RingAlert, GraphDelta
from rules import score_transaction
import graph_detector
from llm_explainer import explain_flag

logger = logging.getLogger("fraud_engine")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(name)s %(levelname)s — %(message)s", datefmt="%H:%M:%S")


N8N_WEBHOOK_URL: str | None = os.environ.get("N8N_WEBHOOK_URL")
if N8N_WEBHOOK_URL:
    logger.info("n8n webhook configured: %s", N8N_WEBHOOK_URL)
else:
    logger.warning("N8N_WEBHOOK_URL not set — /alertflag will log only, no webhook fired")

app = FastAPI(title="Fraud Detection Engine")

# Allow the React dashboard (likely on a different port) to connect freely.
# Fine for a hackathon; lock this down for anything real.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FLAG_THRESHOLD = 0.4
RING_FORCE_SCORE = 0.9

async def _fire_n8n_alert(body: dict) -> None:
    """Fire-and-forget: POST transaction data to the n8n webhook.
    Called via asyncio.create_task so it never blocks the transaction pipeline."""
    if not N8N_WEBHOOK_URL:
        logger.warning("[n8n] N8N_WEBHOOK_URL not set — skipping webhook for txn=%s", body.get("transaction_id"))
        return
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=body)
            resp.raise_for_status()
            logger.info("[n8n] webhook OK (%s) for txn=%s", resp.status_code, body.get("transaction_id"))
    except httpx.HTTPStatusError as e:
        logger.error("[n8n] webhook error %s for txn=%s: %s", e.response.status_code, body.get("transaction_id"), e.response.text[:200])
    except Exception as e:
        logger.error("[n8n] failed to reach webhook for txn=%s: %s", body.get("transaction_id"), e)


def _build_alert_payload(txn: Transaction, score: float, is_flagged: bool, reasons: list[str], explanation: str | None) -> dict:
    """Builds the AlertFlagPayload body from a scored transaction — the
    single place both the automatic (in /transactions) and manual
    (/alertflag) paths construct this shape, so they can never drift apart."""
    payload = AlertFlagPayload(
        transaction_id=txn.transaction_id,
        user_id=txn.user_id,
        amount=txn.amount,
        currency=txn.currency,
        merchant=txn.merchant,
        merchant_category=txn.merchant_category,
        location=txn.location,
        timestamp=txn.timestamp,
        payment_method=txn.payment_method,
        risk_score=round(score, 3),
        is_flagged=is_flagged,
        reasons=reasons,
        explanation=explanation,
    )
    return json.loads(payload.model_dump_json())


class Stats:
    """Running totals for the impact-metrics panel."""

    def __init__(self):
        self.total = 0
        self.flagged = 0
        self.flagged_amount = 0.0
        self.false_positives = 0
        self.confirmed_fraud = 0
        self.rings_detected = 0
        self._latency_sum_ms = 0.0

    def record_transaction(self, txn: Transaction, is_flagged: bool, latency_ms: float):
        self.total += 1
        self._latency_sum_ms += latency_ms
        if is_flagged:
            self.flagged += 1
            self.flagged_amount += txn.amount

    def record_ring(self):
        self.rings_detected += 1

    def record_feedback(self, is_false_positive: bool):
        if is_false_positive:
            self.false_positives += 1
        else:
            self.confirmed_fraud += 1

    def snapshot(self) -> dict:
        avg_latency = (self._latency_sum_ms / self.total) if self.total else 0.0
        flag_rate = (self.flagged / self.total) if self.total else 0.0
        return {
            "total": self.total,
            "flagged": self.flagged,
            "flagged_amount": round(self.flagged_amount, 2),
            "flag_rate": round(flag_rate, 4),
            "false_positives": self.false_positives,
            "confirmed_fraud": self.confirmed_fraud,
            "rings_detected": self.rings_detected,
            "avg_latency_ms": round(avg_latency, 1),
        }


stats = Stats()

class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, payload: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


@app.get("/")
async def root():
    return {"message": "Backend is running"}

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/graph")
async def get_graph_snapshot():
    return graph_detector.snapshot()


@app.get("/stats")
async def get_stats():
    return stats.snapshot()


@app.post("/transactions", response_model=RiskResult)
async def ingest_transaction(txn: Transaction):
    start = time.perf_counter()

    score, reasons, triggered = score_transaction(txn)

    # --- fraud ring check: reasons about the RELATIONSHIP between accounts,
    # not just this one transaction, so it can catch things the rules above
    # never could (see graph_detector.py docstring) ---
    delta, ring_alert = graph_detector.update_graph(txn.user_id, txn.device_id, txn.timestamp)
    ring_flag = None
    if ring_alert:
        ring_flag = RingAlert(**ring_alert)
        linked = ", ".join(ring_alert["linked_users"])
        reasons = reasons + [
            f"Device shared by {len(ring_alert['linked_users'])} distinct users in the last "
            f"{graph_detector.RING_WINDOW_MINUTES} min: {linked}"
        ]
        triggered = triggered + ["fraud_ring"]
        score = max(score, RING_FORCE_SCORE)
        stats.record_ring()

    is_flagged = score >= FLAG_THRESHOLD

    explanation = None
    if is_flagged:
        explanation = await explain_flag(
            user_id=txn.user_id,
            amount=txn.amount,
            merchant=txn.merchant,
            reasons=reasons,
        )

    latency_ms = (time.perf_counter() - start) * 1000
    stats.record_transaction(txn, is_flagged, latency_ms)

    result = RiskResult(
        transaction=txn,
        risk_score=round(score, 3),
        is_flagged=is_flagged,
        reasons=reasons,
        triggered_rules=triggered,
        explanation=explanation,
        ring_flag=ring_flag,
    )

    await manager.broadcast({
        "type": "transaction",
        "data": json.loads(result.model_dump_json()),
        "stats": stats.snapshot(),
    })

    if delta["nodes"] or delta["edges"] or ring_alert:
        graph_payload = GraphDelta(
            nodes=delta["nodes"],
            edges=delta["edges"],
            ring_alert=ring_flag,
        )
        await manager.broadcast({
            "type": "graph",
            "data": json.loads(graph_payload.model_dump_json()),
        })

    # --- n8n alert: fire-and-forget, never blocks the response ---
    if is_flagged:
        alert_body = _build_alert_payload(txn, score, is_flagged, reasons, explanation)
        asyncio.create_task(_fire_n8n_alert(alert_body))

    return result


@app.post("/alertflag")
async def send_alert_flag(payload: AlertFlagPayload):
    """
    Manually (re)fire the n8n webhook for a given flagged transaction —
    lets you test the webhook wiring end-to-end without waiting for a
    live anomaly, or lets an analyst re-send an alert (e.g. adding a
    `note`) after reviewing it on the dashboard.
    """
    body = json.loads(payload.model_dump_json())
    asyncio.create_task(_fire_n8n_alert(body))
    return {"queued": True, "webhook_configured": bool(N8N_WEBHOOK_URL)}


@app.post("/feedback")
async def submit_feedback(fb: FeedbackPayload):
    """
    Analyst marks a flagged transaction as a false positive (or implicitly
    confirms it as real fraud by clicking "Confirm fraud" instead).
    Feeds the impact-metrics panel's false-positive rate.
    """
    stats.record_feedback(fb.is_false_positive)
    print(f"[feedback] txn={fb.transaction_id} false_positive={fb.is_false_positive}")
    return {"received": True}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Dashboard doesn't need to send anything; just keep the connection open.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)