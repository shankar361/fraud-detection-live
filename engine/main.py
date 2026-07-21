"""
Fraud detection engine API.

Two jobs:
1. POST /transactions  -> receives a transaction from the generator,
   scores it, broadcasts the result to all connected dashboards.
2. WS   /ws             -> dashboard clients connect here to receive
   a live feed of scored transactions.

Run with:
    uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import asyncio
import json
import os
import logging
import httpx

from schemas import Transaction, RiskResult, FeedbackPayload, AlertFlagPayload
from rules import score_transaction
from llm_explainer import explain_flag

logger = logging.getLogger("fraud_engine")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(name)s %(levelname)s — %(message)s", datefmt="%H:%M:%S")

# n8n webhook — set N8N_WEBHOOK_URL in your .env or environment before starting uvicorn
# e.g. N8N_WEBHOOK_URL=https://your-n8n-instance.com/webhook/fraud-alert
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


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/transactions", response_model=RiskResult)
async def ingest_transaction(txn: Transaction):
    score, reasons, triggered = score_transaction(txn)
    is_flagged = score >= FLAG_THRESHOLD

    explanation = None
    if is_flagged:
        explanation = await explain_flag(
            user_id=txn.user_id,
            amount=txn.amount,
            merchant=txn.merchant,
            reasons=reasons,
        )

    result = RiskResult(
        transaction=txn,
        risk_score=round(score, 3),
        is_flagged=is_flagged,
        reasons=reasons,
        triggered_rules=triggered,
        explanation=explanation,
    )
    await manager.broadcast(json.loads(result.model_dump_json()))

    # Auto-alert admin via n8n whenever a transaction is flagged
    if is_flagged:
        alert_body = {
            "transaction_id":    txn.transaction_id,
            "user_id":           txn.user_id,
            "amount":            txn.amount,
            "currency":          txn.currency,
            "merchant":          txn.merchant,
            "merchant_category": txn.merchant_category,
            "city":              txn.location.city,
            "country":           txn.location.country,
            "timestamp":         txn.timestamp,
            "payment_method":    txn.payment_method,
            "risk_score":        round(score, 3),
            "is_flagged":        True,
            "reasons":           reasons,
            "explanation":       explanation,
        }
        asyncio.create_task(_fire_n8n_alert(alert_body))
        logger.info("[alertflag] auto-alert queued for txn=%s", txn.transaction_id)

    return result


@app.post("/feedback")
async def submit_feedback(fb: FeedbackPayload):
    """
    Analyst marks a flagged transaction as a false positive.
    For the hackathon demo, we just log it — the natural next step
    (stretch goal) is nudging FLAG_THRESHOLD or per-user thresholds
    based on accumulated feedback.
    """
    print(f"[feedback] txn={fb.transaction_id} false_positive={fb.is_false_positive}")
    return {"received": True}


@app.post("/alertflag")
async def alert_flag(payload: AlertFlagPayload):
    """
    Manually alert admin about a flagged transaction.
    Delegates to the same _fire_n8n_alert helper used by auto-alerts.
    """
    logger.info(
        "[alertflag] manual alert | txn=%s user=%s risk=%.3f",
        payload.transaction_id, payload.user_id, payload.risk_score,
    )
    body = {
        "transaction_id":    payload.transaction_id,
        "user_id":           payload.user_id,
        "amount":            payload.amount,
        "currency":          payload.currency,
        "merchant":          payload.merchant,
        "merchant_category": payload.merchant_category,
        "city":              payload.location.city,
        "country":           payload.location.country,
        "timestamp":         payload.timestamp,
        "payment_method":    payload.payment_method,
        "risk_score":        payload.risk_score,
        "is_flagged":        payload.is_flagged,
        "reasons":           payload.reasons,
        "explanation":       payload.explanation,
        "note":              payload.note,
    }
    if not N8N_WEBHOOK_URL:
        return {"alerted": False, "reason": "N8N_WEBHOOK_URL not configured"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(N8N_WEBHOOK_URL, json=body)
            resp.raise_for_status()
            return {"alerted": True, "n8n_status": resp.status_code}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"n8n webhook error: {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not reach n8n webhook: {e}")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Dashboard doesn't need to send anything; just keep the connection open.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
