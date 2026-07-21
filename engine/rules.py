"""
Rule-based fraud scoring.

Each rule looks at ONE transaction plus the rolling history we've
kept for that user, and returns (triggered: bool, weight: float, reason: str).

We keep per-user state in memory (a simple dict) which is perfectly fine
for a hackathon demo. In production this would live in Redis so it
survives restarts and scales across multiple engine instances.
"""

import math
from datetime import datetime
from collections import defaultdict, deque
from schemas import Transaction

# ---- Tunable thresholds (surface these on the dashboard later if you
#      want the "analyst adjusts sensitivity" stretch goal) ----
VELOCITY_WINDOW_SECONDS = 60
VELOCITY_MAX_TXNS = 3

MAX_PLAUSIBLE_SPEED_KMH = 900 
AMOUNT_ZSCORE_THRESHOLD = 3.0
NEW_MERCHANT_CATEGORY_WEIGHT = 0.15

RULE_WEIGHTS = {
    "velocity": 0.45,
    "impossible_travel": 0.45,
    "amount_deviation": 0.40,
    "new_merchant_category": NEW_MERCHANT_CATEGORY_WEIGHT,
}


class UserHistory:
    """Rolling state we track per user to evaluate rules against."""

    def __init__(self):
        self.recent_txns = deque(maxlen=20)      # Transaction objects, most recent last
        self.amounts = deque(maxlen=50)          # for rolling mean/stddev
        self.known_merchant_categories = set()

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


def check_velocity(user_id: str, txn: Transaction, history: UserHistory):
    now = _parse_ts(txn.timestamp)
    recent = [
        t for t in history.recent_txns
        if (now - _parse_ts(t.timestamp)).total_seconds() <= VELOCITY_WINDOW_SECONDS
    ]
    count = len(recent) + 1  # including this one
    if count > VELOCITY_MAX_TXNS:
        return True, f"{count} transactions within {VELOCITY_WINDOW_SECONDS}s (limit {VELOCITY_MAX_TXNS})"
    return False, None


def check_impossible_travel(user_id: str, txn: Transaction, history: UserHistory):
    if not history.recent_txns:
        return False, None
    last = history.recent_txns[-1]
    now = _parse_ts(txn.timestamp)
    prev_time = _parse_ts(last.timestamp)
    elapsed_hours = max((now - prev_time).total_seconds() / 3600, 1e-6)

    dist_km = _haversine_km(
        last.location.lat, last.location.lon,
        txn.location.lat, txn.location.lon,
    )
    required_speed = dist_km / elapsed_hours

    if required_speed > MAX_PLAUSIBLE_SPEED_KMH and dist_km > 50:
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
    z = (txn.amount - mean) / std
    if z > AMOUNT_ZSCORE_THRESHOLD:
        return True, f"Amount {txn.amount:.0f} is {z:.1f} std devs above user's average ({mean:.0f})"
    return False, None


def check_new_merchant_category(user_id: str, txn: Transaction, history: UserHistory):
    if history.known_merchant_categories and txn.merchant_category not in history.known_merchant_categories:
        return True, f"First-ever transaction in category '{txn.merchant_category}' for this user"
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
        "new_merchant_category": check_new_merchant_category,
    }

    score = 0.0
    reasons = []
    triggered = []

    for rule_id, fn in checks.items():
        hit, reason = fn(txn.user_id, txn, history)
        if hit:
            score += RULE_WEIGHTS[rule_id]
            reasons.append(reason)
            triggered.append(rule_id)

    score = min(score, 1.0)

    # Update rolling state AFTER scoring (so we score against prior behavior, not this txn)
    history.recent_txns.append(txn)
    history.amounts.append(txn.amount)
    history.known_merchant_categories.add(txn.merchant_category)

    return score, reasons, triggered
