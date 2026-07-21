import Header from "./components/Header";
import LiveFeed from "./components/LiveFeed";
import AlertsPanel from "./components/AlertsPanel";
import { useFraudStream } from "./hooks/useFraudStream";
import "./App.css";

export default function App() {
  const { connected, feed, alerts, stats, sendFeedback } = useFraudStream();

  return (
    <div className="app">
      <Header connected={connected} stats={stats} />
      <main>
        <LiveFeed feed={feed} />
        <AlertsPanel alerts={alerts} onFeedback={sendFeedback} />
      </main>
    </div>
  );
}
