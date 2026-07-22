import { useEffect, useRef, useState, useCallback } from "react";

const RAW_BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "https://fraud-detection-be-ruddy.vercel.app";

// Convert http(s) to ws(s) for WebSocket connection
const getWsUrl = (url) => {
  let wsUrl = url.replace(/^http/, "ws");
  if (!wsUrl.endsWith("/ws")) {
    wsUrl = wsUrl.replace(/\/$/, "") + "/ws";
  }
  return wsUrl;
};

const WS_URL = getWsUrl(RAW_BACKEND_URL);
const FEEDBACK_URL = RAW_BACKEND_URL.replace(/\/$/, "") + "/feedback";
const MAX_FEED_ROWS = 40;
const MAX_ALERTS = 15;

/**
 * Owns the WebSocket connection to the fraud engine and keeps
 * the running feed / alert / stat state that the dashboard renders.
 * Auto-reconnects with a fixed backoff if the engine restarts.
 */
export function useFraudStream() {
  const [connected, setConnected] = useState(false);
  const [feed, setFeed] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({ total: 0, flagged: 0 });
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

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
        const result = JSON.parse(event.data);
        handleResult(result);
      };
    }

    function handleResult(result) {
      setStats((s) => ({
        total: s.total + 1,
        flagged: s.flagged + (result.is_flagged ? 1 : 0),
      }));

      setFeed((prev) => [result, ...prev].slice(0, MAX_FEED_ROWS));

      if (result.is_flagged) {
        setAlerts((prev) => [result, ...prev].slice(0, MAX_ALERTS));
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

  return { connected, feed, alerts, stats, sendFeedback };
}
