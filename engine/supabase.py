import logging
import os
import json
import httpx
from dotenv import load_dotenv
load_dotenv()
logger = logging.getLogger("supabase")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_RULE_SETTINGS_TABLE = "rule_settings"
SUPABASE_TRANSACTIONS_TABLE = "transactions"

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    logger.info("Supabase persistence enabled: %s", SUPABASE_URL)
else:
    logger.warning("Supabase persistence disabled because SUPABASE_URL or SUPABASE_SERVICE_KEY is missing")


def _get_supabase_headers() -> dict[str, str] | None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def fetch_rule_settings() -> dict | None:
    headers = _get_supabase_headers()
    if not headers:
        return None

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_RULE_SETTINGS_TABLE}?id=eq.default&select=config"
    try:
        response = httpx.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and data:
            config = data[0].get("config")
            if isinstance(config, dict) and "rules" in config:
                return config
    except Exception:
        pass
    return None


def persist_rule_settings(settings: dict) -> bool:
    headers = _get_supabase_headers()
    if not headers:
        logger.warning("Supabase rule settings save skipped because config is missing")
        return False
    headers["Prefer"] = "resolution=merge-duplicates"

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_RULE_SETTINGS_TABLE}"
    payload = [{"id": "default", "config": settings}]
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        response.raise_for_status()
        logger.info("Supabase rule settings saved successfully")
        return True
    except Exception as exc:
        logger.error("Supabase rule settings save failed: %s", exc)
        return False


def is_supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_KEY)


async def check_supabase_connection() -> dict[str, object]:
    if not is_supabase_configured():
        logger.warning("Supabase status check requested but config is missing")
        return {"configured": False, "connected": False, "reason": "missing configuration"}

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TRANSACTIONS_TABLE}?select=transaction_id&limit=1"
    logger.info("Checking Supabase connectivity with %s", url)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=_get_supabase_headers())
            logger.info("Supabase connectivity response code=%s body=%s", response.status_code, response.text)
            response.raise_for_status()
        return {"configured": True, "connected": True, "status_code": response.status_code}
    except httpx.HTTPStatusError as exc:
        logger.error("Supabase connectivity check failed, status=%s body=%s", exc.response.status_code, exc.response.text)
        return {"configured": True, "connected": False, "status_code": exc.response.status_code, "error": str(exc)}
    except Exception as exc:
        logger.error("Supabase connectivity check failed: %s", exc)
        return {"configured": True, "connected": False, "error": str(exc)}


async def fetch_transactions(limit: int = 40) -> list[dict]:
    headers = _get_supabase_headers()
    if not headers:
        logger.warning("Supabase transaction history fetch skipped because config is missing")
        return []

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TRANSACTIONS_TABLE}?select=*&order=created_at.desc&limit={limit}"
    logger.info("Fetching Supabase transaction history from %s", url)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
        #    logger.info("Supabase transaction history response code=%s body=%s", response.status_code, response.text)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list):
                return [normalize_transaction_row(row) for row in data]
    except Exception as exc:
        logger.error("Supabase transaction history fetch failed: %s", exc)
    return []


def normalize_transaction_row(row: dict) -> dict:
    transaction = {
        "transaction_id": row.get("transaction_id"),
        "user_id": row.get("user_id"),
        "amount": row.get("amount"),
        "currency": row.get("currency"),
        "merchant": row.get("merchant"),
        "merchant_category": row.get("merchant_category"),
        "location": row.get("location"),
        "timestamp": row.get("timestamp"),
        "device_id": row.get("device_id"),
        "payment_method": row.get("payment_method"),
    }

    if isinstance(transaction.get("location"), str):
        try:
            transaction["location"] = json.loads(transaction["location"])
        except Exception:
            pass

    return {
        "transaction": transaction,
        "risk_score": row.get("risk_score"),
        "is_flagged": row.get("is_flagged"),
        "reasons": row.get("reasons") or [],
        "triggered_rules": row.get("triggered_rules") or [],
        "explanation": row.get("explanation"),
        "ring_flag": row.get("ring_flag"),
    }


def _build_supabase_transaction_payload(result: dict) -> dict:
    if isinstance(result.get("transaction"), dict):
        transaction = {**result["transaction"]}
    else:
        transaction = {**result}

    if "transaction" in transaction:
        transaction.pop("transaction", None)

    allowed_columns = {
        "transaction_id",
        "user_id",
        "amount",
        "currency",
        "merchant",
        "merchant_category",
        "location",
        "timestamp",
        "device_id",
        "payment_method",
        "city",
        "risk_score",
        "is_flagged",
        "reasons",
        "triggered_rules",
        "explanation",
        "ring_flag",
    }

    row = {key: transaction[key] for key in transaction if key in allowed_columns}
    if "city" not in row and isinstance(transaction.get("location"), dict):
        row["city"] = transaction["location"].get("city")

    row.update({
        "risk_score": result.get("risk_score"),
        "is_flagged": result.get("is_flagged"),
        "reasons": result.get("reasons"),
        "triggered_rules": result.get("triggered_rules"),
        "explanation": result.get("explanation"),
        "ring_flag": result.get("ring_flag"),
    })

    missing_required = [
        key for key in [
            "transaction_id",
            "user_id",
            "amount",
            "currency",
            "merchant",
            "merchant_category",
            "location",
            "timestamp",
            "device_id",
            "payment_method",
            "risk_score",
            "is_flagged",
            "reasons",
            "triggered_rules",
        ]
        if key not in row
    ]
    if missing_required:
        logger.warning("Supabase transaction payload missing required columns: %s", missing_required)

    if "currency" not in row:
        row["currency"] = "INR"

    return row


async def persist_transaction(payload: dict) -> bool:
    headers = _get_supabase_headers()
    logger.info("persist_transaction called, transaction_id=%s, headers=%s", payload.get("transaction_id") or payload.get("transaction", {}).get("transaction_id"), bool(headers))
    if not headers:
        logger.warning("Supabase transaction save skipped because config is missing")
        return False
    headers["Prefer"] = "return=minimal"

    row = _build_supabase_transaction_payload(payload)
    logger.info("Supabase transaction row keys: %s", list(row.keys()))
    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_TRANSACTIONS_TABLE}"
    logger.info("Supabase transaction POST %s", url)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, headers=headers, json=[row])
            logger.info("Supabase transaction response code=%s body=%s", response.status_code, response.text)
            response.raise_for_status()
        logger.info("Supabase transaction saved %s", row.get("transaction_id"))
        return True
    except Exception as exc:
        logger.error("Supabase transaction save failed %s: %s", row.get("transaction_id"), exc)
        return False
