export default function Header({ connected, stats, onToggleSettings }) {
  const {
    total = 0,
    flagged = 0,
    flagged_amount = 0,
    false_positives = 0,
    confirmed_fraud = 0,
    rings_detected = 0,
    flag_rate = 0,
  } = stats || {};

  return (
    <header className="header">
      <div className="header-top">
        <div className="brand">
          <span className={`dot ${connected ? "" : "disconnected"}`} />
          <div>
            <h1>Live fraud detection</h1>
            <span className="status-text">
              {connected ? "connected — streaming live" : "disconnected — retrying…"}
            </span>
          </div>
        </div>
      </div>

      <div className="header-bottom">
        <div className="stats-grid stats-grid-large">
        <div className="metric-card">
          <div className="metric-label">Transactions</div>
          <div className="metric-value">{total}</div>
        </div>
        <div className="metric-card flagged-card">
          <div className="metric-label">Flagged</div>
          <div className="metric-value">{flagged}</div>
          <div className="metric-help">{Math.round(flag_rate * 100)}%</div>
        </div>
        <div className="metric-card amount-card">
          <div className="metric-label">Flagged amount</div>
          <div className="metric-value">₹{Math.round(flagged_amount).toLocaleString("en-IN")}</div>
        </div>
        <div className="metric-card ring-card">
          <div className="metric-label">Active ring alerts</div>
          <div className="metric-value">{rings_detected}</div>
        </div>
        <div className="metric-card confirm-card">
          <div className="metric-label">Confirmed fraud</div>
          <div className="metric-value">{confirmed_fraud}</div>
        </div>
        <div className="metric-card fp-card">
          <div className="metric-label">False positives</div>
          <div className="metric-value">{false_positives}</div>
        </div>
      </div>

      <button className="settings-toggle" onClick={onToggleSettings} aria-label="Toggle rule settings">
        ☰
      </button>
    </div>
    </header>
  );
}
