import Header from "./components/Header";
import LiveFeed from "./components/LiveFeed";
import AlertsPanel from "./components/AlertsPanel";
import GraphPanel from "./components/GraphPanel";
import { useFraudStream } from "./hooks/useFraudStream";
import "./App.css";

export default function App() {
  const {
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
  } = useFraudStream();

  return (
    <div className="app">
      <Header connected={connected} stats={stats} />
      <GraphPanel
        graphNodes={graphNodes}
        graphEdges={graphEdges}
        ringDeviceIds={ringDeviceIds}
        ringUserIds={ringUserIds}
        ringAlerts={ringAlerts}
        ringsDetected={stats.rings_detected}
      />
      <main>
        <LiveFeed feed={feed} />
        <AlertsPanel alerts={alerts} onFeedback={sendFeedback} />
      </main>
    </div>
  );
}