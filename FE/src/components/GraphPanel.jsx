import GraphView from "./GraphView";
import RingAlertsList from "./RingAlertsList";

export default function GraphPanel({ graphNodes, graphEdges, ringDeviceIds, ringUserIds, ringAlerts, ringsDetected }) {
  return (
    <section className="graph-panel">
      <div className="graph-panel-main">
        <div className="col-title">
          <span>Fraud Ring Network</span>
          <span className="rings-count">{ringsDetected} ring{ringsDetected === 1 ? "" : "s"} detected</span>
        </div>
        <div className="graph-legend">
          <span className="legend-item"><span className="legend-swatch user" /> user</span>
          <span className="legend-item"><span className="legend-swatch device" /> device</span>
          <span className="legend-item"><span className="legend-swatch ring" /> part of a ring</span>
        </div>
        <GraphView
          nodes={graphNodes}
          edges={graphEdges}
          ringDeviceIds={ringDeviceIds}
          ringUserIds={ringUserIds}
        />
      </div>
      <RingAlertsList ringAlerts={ringAlerts} />
    </section>
  );
}
