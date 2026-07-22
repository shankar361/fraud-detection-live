import { useState } from "react";

function formatAmount(amount) {
  return Math.round(amount).toLocaleString("en-IN");
}

function formatTime(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  return d.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function TxnRow({ result, isExpanded, onToggle }) {
  if (!result || !result.transaction) return null;
  const { transaction, risk_score, is_flagged, reasons, explanation } = result;
  const payMethod = transaction.payment_method?.replace("card_ending_", "···") ?? "—";
  
  return (
    <div 
      className={`txn-row clickable ${is_flagged ? "flagged" : ""} ${isExpanded ? "expanded" : ""}`}
      onClick={onToggle}
    >
      <span className="ts">{formatTime(transaction.timestamp)}</span>
      <span className="uid">{transaction.user_id}</span>
      <span className="amt">₹{formatAmount(transaction.amount)}</span>
      <span className="city">{transaction.location.city}</span>
      <span className="merchant">{transaction.merchant}</span>
      <span className="pay-method">{payMethod}</span>
      <span className={`risk ${is_flagged ? "high" : "low"}`}>
        {Math.round(risk_score * 100)}%
      </span>
      <span className="reason">{reasons.join(" · ") || "—"}</span>
      
      {isExpanded && (
        <div className="txn-details" onClick={(e) => e.stopPropagation()}>
          <div className="details-grid">
            <div className="details-group">
              <strong>Transaction ID</strong>
              <code>{transaction.transaction_id}</code>
            </div>
            <div className="details-group">
              <strong>Category</strong>
              <span>{transaction.merchant_category}</span>
            </div>
            <div className="details-group">
              <strong>Device ID</strong>
              <code>{transaction.device_id}</code>
            </div>
            <div className="details-group">
              <strong>Location Coordinate</strong>
              <span>{transaction.location.lat.toFixed(4)}, {transaction.location.lon.toFixed(4)}</span>
            </div>
            
            {explanation && (
              <div className="details-group full-width">
                <strong>AI Explanation</strong>
                <p className="details-explanation">{explanation}</p>
              </div>
            )}
            
            <div className="details-group full-width">
              <strong>Triggered Signals</strong>
              <ul className="details-signals-list">
                {reasons.length > 0 ? (
                  reasons.map((r, idx) => <li key={idx}>{r}</li>)
                ) : (
                  <li>No anomalous signals triggered (normal transaction)</li>
                )}
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function LiveFeed({ feed }) {
  const [expandedTxnId, setExpandedTxnId] = useState(null);

  const handleToggle = (id) => {
    setExpandedTxnId((prevId) => (prevId === id ? null : id));
  };

  return (
    <div className="feed-col">
      <div className="col-title">
        <span>Live Feed</span>
      </div>
      <div className="txn-header">
        <span>Time</span>
        <span>User</span>
        <span>Amount</span>
        <span>City</span>
        <span>Merchant</span>
        <span>Pay Method</span>
        <span>Risk</span>
        <span>Signals</span>
      </div>
      {feed.length === 0 && (
        <div className="empty-state">Waiting for transactions…</div>
      )}
      {feed.map((result) => {
        const txnId = result?.transaction?.transaction_id;
        if (!txnId) return null;
        return (
          <TxnRow
            key={txnId}
            result={result}
            isExpanded={expandedTxnId === txnId}
            onToggle={() => handleToggle(txnId)}
          />
        );
      })}
    </div>
  );
}
