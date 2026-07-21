import { useState } from "react";

function formatAmount(amount) {
  return Math.round(amount).toLocaleString("en-IN");
}

function AlertCard({ result, onFeedback }) {
  const { transaction, risk_score, reasons, explanation } = result;
  const [actionTaken, setActionTaken] = useState(null); // null | "confirm" | "dismiss"

  function handleClick(action) {
    setActionTaken(action);
    onFeedback(transaction.transaction_id, action === "dismiss");
  }

  return (
    <div className="alert-card">
      <div className="top-row">
        <span className="uid">{transaction.user_id}</span>
        <span className="score">risk {Math.round(risk_score * 100)}%</span>
      </div>
      <div className="amt">
        ₹{formatAmount(transaction.amount)} · {transaction.merchant} · {transaction.location.city}
      </div>
      {explanation && <p className="explanation">{explanation}</p>}
      <details className="raw-reasons">
        <summary>Raw signals</summary>
        <ul>
          {reasons.map((reason, i) => (
            <li key={i}>{reason}</li>
          ))}
        </ul>
      </details>
      <div className="actions">
        <button
          className={actionTaken && actionTaken !== "confirm" ? "dismissed" : ""}
          onClick={() => handleClick("confirm")}
        >
          {actionTaken === "confirm" ? "Confirmed ✓" : "Confirm fraud"}
        </button>
        <button
          className={actionTaken && actionTaken !== "dismiss" ? "dismissed" : ""}
          onClick={() => handleClick("dismiss")}
        >
          {actionTaken === "dismiss" ? "Marked false positive ✓" : "Mark false positive"}
        </button>
      </div>
    </div>
  );
}

export default function AlertsPanel({ alerts, onFeedback }) {
  return (
    <div className="alerts-col">
      <div className="col-title">Active Alerts</div>
      {alerts.length === 0 && (
        <div className="empty-state">No alerts yet — waiting for anomalies…</div>
      )}
      {alerts.map((result) => (
        <AlertCard
          key={result.transaction.transaction_id}
          result={result}
          onFeedback={onFeedback}
        />
      ))}
    </div>
  );
}
