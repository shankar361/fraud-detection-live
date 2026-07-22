"""
Fraud ring detection.

Individual rule-based scoring (velocity, geo-jump, amount deviation) looks
at ONE transaction at a time. That completely misses organized fraud rings
and mule networks, where each individual transaction looks perfectly
normal, but several "unrelated" accounts are secretly connected — e.g.
sharing the same device.

This module tracks a live graph of user <-> device relationships and
flags when a single device is suddenly linked to several distinct users
within a short time window, a classic signal for fake-account farms /
mule networks that per-transaction rules cannot see.
"""

import networkx as nx
from collections import defaultdict
from datetime import datetime, timedelta

RING_WINDOW_MINUTES = 30
RING_USER_THRESHOLD = 3  # distinct users on one device within the window -> ring

# In-memory graph for the whole demo session. Nodes are user_ids and
# device_ids (distinguished by a "type" attribute); edges mean
# "this user transacted from this device".
graph = nx.Graph()

# device_id -> list of (user_id, timestamp) — used to compute the
# rolling "distinct users in the last N minutes" window per device.
_device_user_events: dict[str, list] = defaultdict(list)
_active_ring_devices: set[str] = set()


def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def update_graph(user_id: str, device_id: str, timestamp: str):
    """
    Call once per transaction. Updates the in-memory graph and the
    per-device rolling user history.

    Returns (delta, ring_alert):
      - delta: dict with only the NEW nodes/edges this call added
        (so the frontend can apply incremental updates instead of
        redrawing the whole graph every transaction).
      - ring_alert: dict if this device just crossed the ring threshold,
        else None.
    """
    now = _parse_ts(timestamp)

    is_new_user_node = user_id not in graph
    is_new_device_node = device_id not in graph
    is_new_edge = not graph.has_edge(user_id, device_id)

    graph.add_node(user_id, type="user")
    graph.add_node(device_id, type="device")
    graph.add_edge(user_id, device_id)

    # Update rolling window of which users have used this device recently.
    events = _device_user_events[device_id]
    events.append((user_id, now))
    cutoff = now - timedelta(minutes=RING_WINDOW_MINUTES)
    _device_user_events[device_id] = [(u, t) for (u, t) in events if t >= cutoff]
    distinct_users = sorted({u for u, _ in _device_user_events[device_id]})

    delta_nodes = []
    if is_new_user_node:
        delta_nodes.append({"id": user_id, "type": "user"})
    if is_new_device_node:
        delta_nodes.append({"id": device_id, "type": "device"})

    delta_edges = []
    if is_new_edge:
        delta_edges.append({"source": user_id, "target": device_id})

    ring_alert = None
    device_has_ring = len(distinct_users) >= RING_USER_THRESHOLD

    if device_has_ring and device_id not in _active_ring_devices:
        _active_ring_devices.add(device_id)
        ring_alert = {
            "device_id": device_id,
            "linked_users": distinct_users,
            "detected_at": timestamp,
        }
    elif not device_has_ring and device_id in _active_ring_devices:
        _active_ring_devices.remove(device_id)

    delta = {"nodes": delta_nodes, "edges": delta_edges}
    return delta, ring_alert


def _active_ring_user_ids() -> set[str]:
    return {u for device_id in _active_ring_devices for u, _ in _device_user_events.get(device_id, [])}


def snapshot():
    """Full current graph state, for a newly-connected dashboard client."""
    nodes = [
        {"id": n, "type": graph.nodes[n].get("type", "unknown")}
        for n in graph.nodes
    ]
    edges = [{"source": u, "target": v} for u, v in graph.edges]

    active_ring_users = _active_ring_user_ids()
    return {
        "nodes": nodes,
        "edges": edges,
        "ring_device_count": len(_active_ring_devices),
        "ring_user_count": len(active_ring_users),
        "ring_device_ids": sorted(_active_ring_devices),
        "ring_user_ids": sorted(active_ring_users),
    }
