import { useEffect, useRef, useState, useCallback } from "react";

const RAW_BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

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
const MAX_FEED_ROWS = 40;
const MAX_ALERTS = 15;

/**
 * Owns the WebSocket connection to the fraud engine and keeps
 * the running feed / alert / stat / graph state that the dashboard renders.
 * Auto-reconnects with a fixed backoff if the engine restarts.
 */
export function useFraudStream() {
  const [connected, setConnected] = useState(false);
  const [feed, setFeed] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({ total: 0, flagged: 0, rings_detected: 0 });
  const [graphNodes, setGraphNodes] = useState([]);
  const [graphEdges, setGraphEdges] = useState([]);
  const [ringAlerts, setRingAlerts] = useState([]);

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
        if (Array.isArray(data.ring_alerts)) setRingAlerts(data.ring_alerts);
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
        const { nodes = [], edges = [], ring_alert } = msg.data || {};

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

  const ringDeviceIds = new Set(ringAlerts.map((a) => a.device_id));
  const ringUserIds = new Set(ringAlerts.flatMap((a) => a.linked_users || []));

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
