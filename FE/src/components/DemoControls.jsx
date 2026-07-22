import { useState } from "react";

const BACKEND_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

async function triggerDemo(path) {
  const response = await fetch(`${BACKEND_BASE}${path}`, { method: "POST" });
  if (!response.ok) {
    throw new Error("Demo action failed");
  }
  return response.json();
}

export default function DemoControls() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const handleClick = async (path, label) => {
    setLoading(true);
    setStatus(null);
    setMessage(`Running ${label}...`);
    try {
      const result = await triggerDemo(path);
      setStatus("success");
      setMessage(`${label} triggered: ${result.demo}`);
    } catch (error) {
      setStatus("error");
      setMessage(`${label} failed`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="demo-controls">
      <div className="demo-header">
        <div>
          <div className="demo-label">Demo Controls</div>
          <div className="demo-description">Trigger live scenarios to showcase ring detection and anomaly scoring.</div>
        </div>
      </div>
      <div className="demo-actions">
        <button
          className="demo-button ring-button"
          onClick={() => handleClick("/demo/ring", "Ring attack")}
          disabled={loading}
        >
          Trigger ring attack
        </button>
        <button
          className="demo-button anomaly-button"
          onClick={() => handleClick("/demo/anomaly", "Anomaly burst")}
          disabled={loading}
        >
          Inject anomaly transaction
        </button>
      </div>
      {message && (
        <div className={`demo-message ${status || "info"}`}>{message}</div>
      )}
    </div>
  );
}
