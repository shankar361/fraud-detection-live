export default function Header({ connected, stats }) {
  return (
    <header className="header">
      <div className="brand">
        <span className={`dot ${connected ? "" : "disconnected"}`} />
        <h1>Live fraud detection</h1>
        <span className="status-text">
          {connected ? "connected — streaming live" : "disconnected — retrying…"}
        </span>
      </div>
      <div className="stats">
        <div className="stat">
          <div className="num">{stats.total}</div>
          <div className="label">Transactions</div>
        </div>
        <div className="stat flagged-stat">
          <div className="num">{stats.flagged}</div>
          <div className="label">Flagged</div>
        </div>
      </div>
    </header>
  );
}
