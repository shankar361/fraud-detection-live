import { useEffect, useRef, useState, useCallback } from "react";

const RAW_BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || "http://localhost:8000").replace(/\/+$|^$/, "");
console.log("VITE_BACKEND_URL", RAW_BACKEND_URL);
console.log("import.meta.env.VITE_BACKEND_URL", import.meta.env.VITE_BACKEND_URL);
// Convert http(s) to ws(s) for WebSocket connection
const getWsUrl = (url) => {
  let wsUrl = url.replace(/^http/, "ws");
  if (!wsUrl.endsWith("/ws")) {
    wsUrl = wsUrl.replace(/\/$/, "") + "/ws";
  }
  return wsUrl;
};

const WS_URL = import.meta.env.VITE_WS_URL || getWsUrl(RAW_BACKEND_URL);
const BASE_HTTP_URL = RAW_BACKEND_URL.replace(/\/$/, "");
const FEEDBACK_URL = `${BASE_HTTP_URL}/feedback`;
const GRAPH_URL = `${BASE_HTTP_URL}/graph`;
const MAX_FEED_ROWS = 30;
const MAX_ALERTS = 15;
console.log("WS_URL", WS_URL);
console.log("BASE_HTTP_URL", BASE_HTTP_URL);
console.log("FEEDBACK_URL", FEEDBACK_URL);
console.log("GRAPH_URL", GRAPH_URL);  
/**
 * Owns the WebSocket connection to the fraud engine and keeps
 * the running feed / alert / stat / graph state that the dashboard renders.
 * Auto-reconnects with a fixed backoff if the engine restarts.
 */
export function useFraudStream() {
  const [connected, setConnected] = useState(false);
  const [feed, setFeed] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    flagged: 0,
    flagged_amount: 0,
    flag_rate: 0,
    false_positives: 0,
    confirmed_fraud: 0,
    rings_detected: 0,
    avg_latency_ms: 0,
  });
  const [graphNodes, setGraphNodes] = useState([]);
  const [graphEdges, setGraphEdges] = useState([]);
  const [ringAlerts, setRingAlerts] = useState([]);
  const [ringDeviceIds, setRingDeviceIds] = useState(new Set());
  const [ringUserIds, setRingUserIds] = useState(new Set());

  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  // Fetch initial graph snapshot on mount
  useEffect(() => {
    fetch(GRAPH_URL)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        if (Array.isArray(data.nodes)) setGraphNodes(data.nodes);
        if (Array.isArray(data.edges)) setGraphEdges(data.edges);
        if (Array.isArray(data.ring_device_ids)) {
          setRingDeviceIds(new Set(data.ring_device_ids));
        }
        if (Array.isArray(data.ring_user_ids)) {
          setRingUserIds(new Set(data.ring_user_ids));
        }
        if (Array.isArray(data.ring_alerts)) setRingAlerts(data.ring_alerts);
      })
      .catch(() => {});

    fetch(`${BASE_HTTP_URL}/transactions/history?limit=${MAX_FEED_ROWS}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (!Array.isArray(data)) return;
        setFeed(data);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;

    function connect() {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => !cancelled && setConnected(true);

      ws.onclose = () => {
        if (cancelled) return;
        setConnected(false);
        reconnectTimer.current = setTimeout(connect, 2000);
      };

      ws.onerror = () => ws.close();

      ws.onmessage = (event) => {
        if (cancelled) return;
        try {
          const result = JSON.parse(event.data);
          handleResult(result);
        } catch (e) {
          // ignore non-json messages
        }
      };
    }

    function handleResult(msg) {
      if (!msg) return;

      let item = msg;
      if (msg.type === "transaction") {
        item = msg.data;
        if (msg.stats) {
          setStats(msg.stats);
        }
      } else if (msg.type === "graph") {
        const { nodes = [], edges = [], ring_alert, ring_device_ids, ring_user_ids } = msg.data || {};

        if (nodes.length > 0) {
          setGraphNodes((prev) => {
            const existingIds = new Set(prev.map((n) => n.id));
            const newNodes = nodes.filter((n) => !existingIds.has(n.id));
            return newNodes.length > 0 ? [...prev, ...newNodes] : prev;
          });
        }

        if (edges.length > 0) {
          setGraphEdges((prev) => {
            const existingKeys = new Set(prev.map((e) => `${e.source}-${e.target}`));
            const newEdges = edges.filter((e) => !existingKeys.has(`${e.source}-${e.target}`));
            return newEdges.length > 0 ? [...prev, ...newEdges] : prev;
          });
        }

        if (Array.isArray(ring_device_ids)) {
          setRingDeviceIds(new Set(ring_device_ids));
        }

        if (Array.isArray(ring_user_ids)) {
          setRingUserIds(new Set(ring_user_ids));
        }

        if (ring_alert) {
          setRingAlerts((prev) => {
            const exists = prev.some((a) => a.device_id === ring_alert.device_id && a.detected_at === ring_alert.detected_at);
            return exists ? prev : [ring_alert, ...prev];
          });
        }
        return;
      }

      if (!item || !item.transaction) return;

      if (!msg.stats) {
        setStats((s) => ({
          ...s,
          total: s.total + 1,
          flagged: s.flagged + (item.is_flagged ? 1 : 0),
        }));
      }

      if (item.ring_flag) {
        setRingAlerts((prev) => {
          const exists = prev.some((a) => a.device_id === item.ring_flag.device_id && a.detected_at === item.ring_flag.detected_at);
          return exists ? prev : [item.ring_flag, ...prev];
        });
      }

      setFeed((prev) => [item, ...prev].slice(0, MAX_FEED_ROWS));

      if (item.is_flagged) {
        setAlerts((prev) => [item, ...prev].slice(0, MAX_ALERTS));
      }
    }

    connect();

    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, []);

  const sendFeedback = useCallback((transactionId, isFalsePositive) => {
    fetch(FEEDBACK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transaction_id: transactionId,
        is_false_positive: isFalsePositive,
      }),
    }).catch(() => {
      // Best-effort for a hackathon demo — silently ignore network hiccups.
    });
  }, []);

  return {
    connected,
    feed,
    alerts,
    stats,
    sendFeedback,
    graphNodes,
    graphEdges,
    ringDeviceIds,
    ringUserIds,
    ringAlerts,
  };
}
