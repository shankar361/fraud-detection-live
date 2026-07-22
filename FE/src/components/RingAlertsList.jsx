function timeAgo(isoString) {
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(isoString).getTime()) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes}m ago`;
}

export default function RingAlertsList({ ringAlerts = [] }) {
  const alerts = Array.isArray(ringAlerts) ? ringAlerts : [];

  return (
    <div className="ring-alerts">
      <div className="col-title">Detected Rings</div>
      {alerts.length === 0 && (
        <div className="empty-state">No rings detected yet.</div>
      )}
      {alerts.map((alert, i) => (
        <div className="ring-alert-card" key={`${alert?.device_id || i}-${alert?.detected_at || i}-${i}`}>
          <div className="ring-alert-top">
            <span className="ring-device">{alert?.device_id}</span>
            <span className="ring-time">{alert?.detected_at ? timeAgo(alert.detected_at) : "recently"}</span>
          </div>
          <div className="ring-users">
            {(alert?.linked_users || []).length} linked users: {(alert?.linked_users || []).join(", ")}
          </div>
        </div>
      ))}
    </div>
  );
}
