"""
Data models for the fraud detection engine.
Keeping these in one place so the generator, rules engine, and API
all agree on the exact same shape.
"""

from pydantic import BaseModel
from typing import Optional, List


class Location(BaseModel):
    city: str
    country: str
    lat: float
    lon: float


class Transaction(BaseModel):
    transaction_id: str
    user_id: str
    amount: float
    currency: str = "INR"
    merchant: str
    merchant_category: str
    location: Location
    timestamp: str  # ISO 8601
    device_id: str
    payment_method: str


class RingAlert(BaseModel):
    device_id: str
    linked_users: List[str]
    detected_at: str


class RiskResult(BaseModel):
    transaction: Transaction
    risk_score: float          # 0.0 - 1.0
    is_flagged: bool
    reasons: List[str]         # human-readable triggered rules (raw)
    triggered_rules: List[str] # machine-readable rule ids
    explanation: Optional[str] = None  # LLM-generated one-liner, only set when flagged
    ring_flag: Optional[RingAlert] = None  # set when this txn's device is part of a detected ring


class GraphNode(BaseModel):
    id: str
    type: str  # "user" | "device"


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphDelta(BaseModel):
    nodes: List[GraphNode] = []
    edges: List[GraphEdge] = []
    ring_alert: Optional[RingAlert] = None


class FeedbackPayload(BaseModel):
    transaction_id: str
    is_false_positive: bool


class AlertFlagPayload(BaseModel):
    """Body sent to POST /alertflag — wraps the full risk result so the
    caller doesn't have to re-fetch anything."""
    transaction_id: str
    user_id: str
    amount: float
    currency: str
    merchant: str
    merchant_category: str
    location: Location
    timestamp: str
    payment_method: str
    risk_score: float
    is_flagged: bool
    reasons: List[str]
    explanation: Optional[str] = None
    note: Optional[str] = None   # optional analyst comment