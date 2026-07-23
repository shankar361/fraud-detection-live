"""
Rule-based fraud scoring.

Each rule looks at ONE transaction plus the rolling history we've
kept for that user, and returns (triggered: bool, weight: float, reason: str).

We keep per-user state in memory (a simple dict) which is perfectly fine
for a hackathon demo. In production this would live in Redis so it
survives restarts and scales across multiple engine instances.
"""

import json
import math
import os
import tempfile
from datetime import datetime
from collections import defaultdict, deque
from pathlib import Path
import httpx
from schemas import Transaction

RULE_SETTINGS_PATH = Path(__file__).resolve().parent / "rule_settings.json"
FALLBACK_RULE_SETTINGS_PATH = Path(tempfile.gettempdir()) / "rule_settings.json"
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_RULE_SETTINGS_TABLE = "rule_settings"

DEFAULT_RULE_SETTINGS = {
    "flag_threshold_pct": 40.0,
    "rules": {
        "velocity": {
            "enabled": True,
            "weight": 0.45,
            "window_seconds": 60,
            "max_txns": 3,
        },
        "impossible_travel": {
            "enabled": True,
            "weight": 0.45,
            "max_speed_kmh": 900,
            "min_distance_km": 50,
        },
        "amount_deviation": {
            "enabled": True,
            "weight": 0.4,
            "zscore_threshold": 3.0,
        },
        "transaction_distance": {
            "enabled": True,
            "weight": 0.25,
            "min_distance_km": 500,
        },
        "new_payment_method": {
            "enabled": True,
            "weight": 0.2,
        },
        "new_merchant_category": {
            "enabled": True,
            "weight": 0.15,
        },
        "country_mismatch": {
            "enabled": False,
            "weight": 0.25,
        },
    }
}

RULE_SETTINGS = {}


class UserHistory:
    """Rolling state we track per user to evaluate rules against."""

    def __init__(self):
        self.recent_txns = deque(maxlen=20)      # Transaction objects, most recent last
        self.amounts = deque(maxlen=50)          # for rolling mean/stddev
        self.known_merchant_categories = set()
        self.known_payment_methods = set()

    def rolling_mean_std(self):
        if len(self.amounts) < 2:
            return None, None
        mean = sum(self.amounts) / len(self.amounts)
        variance = sum((a - mean) ** 2 for a in self.amounts) / len(self.amounts)
        return mean, math.sqrt(variance)


# user_id -> UserHistory
_user_state: dict[str, UserHistory] = defaultdict(UserHistory)


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points, in km."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _get_supabase_headers() -> dict[str, str] | None:
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None
    return {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _load_rule_settings_from_supabase() -> dict | None:
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


def _load_rule_settings() -> dict:
    settings = _load_rule_settings_from_supabase()
    if settings is not None:
        return settings

    for path in (RULE_SETTINGS_PATH, FALLBACK_RULE_SETTINGS_PATH):
        try:
            with path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if not isinstance(loaded, dict) or "rules" not in loaded:
                raise ValueError("Invalid rule settings format")
            return loaded
        except Exception:
            continue

    return DEFAULT_RULE_SETTINGS.copy()


def get_rule_settings() -> dict:
    return RULE_SETTINGS


def _save_rule_settings_to_supabase(settings: dict) -> bool:
    headers = _get_supabase_headers()
    if not headers:
        return False

    url = f"{SUPABASE_URL}/rest/v1/{SUPABASE_RULE_SETTINGS_TABLE}"
    payload = [{"id": "default", "config": settings}]
    headers["Prefer"] = "resolution=merge-duplicates"

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
        response.raise_for_status()
        return True
    except Exception:
        return False


def save_rule_settings(settings: dict) -> dict:
    global RULE_SETTINGS
    if _save_rule_settings_to_supabase(settings):
        RULE_SETTINGS = settings
        return RULE_SETTINGS

    try:
        with RULE_SETTINGS_PATH.open("w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        RULE_SETTINGS = _load_rule_settings()
        return RULE_SETTINGS
    except Exception:
        with FALLBACK_RULE_SETTINGS_PATH.open("w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        RULE_SETTINGS = settings
        return RULE_SETTINGS


RULE_SETTINGS = _load_rule_settings()


def _rule_config(rule_id: str, key: str, default=None):
    return RULE_SETTINGS.get("rules", {}).get(rule_id, {}).get(key, default)


def check_velocity(user_id: str, txn: Transaction, history: UserHistory):
    window_seconds = _rule_config("velocity", "window_seconds", 60)
    max_txns = _rule_config("velocity", "max_txns", 3)
    now = _parse_ts(txn.timestamp)
    recent = [
        t for t in history.recent_txns
        if (now - _parse_ts(t.timestamp)).total_seconds() <= window_seconds
    ]
    count = len(recent) + 1  # including this one
    if count > max_txns:
        return True, f"{count} transactions within {window_seconds}s (limit {max_txns})"
    return False, None


def check_impossible_travel(user_id: str, txn: Transaction, history: UserHistory):
    if not history.recent_txns:
        return False, None
    max_speed_kmh = _rule_config("impossible_travel", "max_speed_kmh", 900)
    min_distance_km = _rule_config("impossible_travel", "min_distance_km", 50)

    last = history.recent_txns[-1]
    now = _parse_ts(txn.timestamp)
    prev_time = _parse_ts(last.timestamp)
    elapsed_hours = max((now - prev_time).total_seconds() / 3600, 1e-6)

    dist_km = _haversine_km(
        last.location.lat, last.location.lon,
        txn.location.lat, txn.location.lon,
    )
    required_speed = dist_km / elapsed_hours

    if required_speed > max_speed_kmh and dist_km > min_distance_km:
        return True, (
            f"{dist_km:.0f}km from last transaction "
            f"({last.location.city} -> {txn.location.city}) in "
            f"{elapsed_hours*60:.1f} min — implies {required_speed:.0f} km/h travel"
        )
    return False, None


def check_amount_deviation(user_id: str, txn: Transaction, history: UserHistory):
    mean, std = history.rolling_mean_std()
    if mean is None or std == 0:
        return False, None
    threshold = _rule_config("amount_deviation", "zscore_threshold", 3.0)
    z = (txn.amount - mean) / std
    if z > threshold:
        return True, f"Amount {txn.amount:.0f} is {z:.1f} std devs above user's average ({mean:.0f})"
    return False, None


def check_transaction_distance(user_id: str, txn: Transaction, history: UserHistory):
    if not history.recent_txns:
        return False, None

    last = history.recent_txns[-1]
    dist_km = _haversine_km(
        last.location.lat, last.location.lon,
        txn.location.lat, txn.location.lon,
    )
    if dist_km < 1:
        return False, None

    threshold_km = _rule_config("transaction_distance", "min_distance_km", 500)
    if dist_km > threshold_km:
        return True, f"Transaction is {dist_km:.0f} km away from last location"
    return False, None


def check_new_merchant_category(user_id: str, txn: Transaction, history: UserHistory):
    if history.known_merchant_categories and txn.merchant_category not in history.known_merchant_categories:
        return True, f"First-ever transaction in category '{txn.merchant_category}' for this user"
    return False, None


def check_new_payment_method(user_id: str, txn: Transaction, history: UserHistory):
    if history.known_payment_methods and txn.payment_method not in history.known_payment_methods:
        return True, f"First use of payment method '{txn.payment_method}' for this user"
    return False, None


def check_country_mismatch(user_id: str, txn: Transaction, history: UserHistory):
    if not history.recent_txns:
        return False, None
    last = history.recent_txns[-1]
    if txn.location.country != last.location.country:
        return True, (
            f"Country changed from {last.location.country} to {txn.location.country} "
            f"since last transaction"
        )
    return False, None


def score_transaction(txn: Transaction) -> tuple[float, list[str], list[str]]:
    """
    Runs all rules against the transaction, using and then updating
    that user's rolling history. Returns (risk_score, reasons, triggered_rule_ids).
    """
    history = _user_state[txn.user_id]

    checks = {
        "velocity": check_velocity,
        "impossible_travel": check_impossible_travel,
        "amount_deviation": check_amount_deviation,
        "transaction_distance": check_transaction_distance,
        "new_payment_method": check_new_payment_method,
        "new_merchant_category": check_new_merchant_category,
        "country_mismatch": check_country_mismatch,
    }

    score = 0.0
    reasons = []
    triggered = []

    for rule_id, fn in checks.items():
        rule_cfg = RULE_SETTINGS.get("rules", {}).get(rule_id, {})
        if not rule_cfg.get("enabled", True):
            continue

        hit, reason = fn(txn.user_id, txn, history)
        if hit:
            score += rule_cfg.get("weight", 0.0)
            reasons.append(reason)
            triggered.append(rule_id)

    score = min(score, 1.0)

    # Update rolling state AFTER scoring (so we score against prior behavior, not this txn)
    history.recent_txns.append(txn)
    history.amounts.append(txn.amount)
    history.known_merchant_categories.add(txn.merchant_category)
    history.known_payment_methods.add(txn.payment_method)

    return score, reasons, triggered
