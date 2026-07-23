import { useRef } from "react";
import GraphView from "./GraphView";
import RingAlertsList from "./RingAlertsList";

export default function GraphPanel({ graphNodes, graphEdges, ringDeviceIds, ringUserIds, ringAlerts, ringsDetected }) {
  const resetZoomRef = useRef(null);

  return (
    <section className="graph-panel">
      <div className="graph-panel-main">
        <div className="col-title">
          <span>Fraud Ring Network</span>
          <span className="rings-count">{ringsDetected} ring{ringsDetected === 1 ? "" : "s"} detected</span>
        </div>
        <div className="graph-controls">
          <button type="button" onClick={() => resetZoomRef.current?.reset()}>Reset zoom</button>
        </div>
        <div className="graph-summary">
          <span>{graphNodes.length} nodes</span>
          <span>{graphEdges.length} edges</span>
          <span>{ringDeviceIds.size} ring devices</span>
          <span>{ringUserIds.size} ring users</span>
        </div>
        <div className="graph-legend">
          <span className="legend-item"><span className="legend-swatch user" /> user node</span>
          <span className="legend-item"><span className="legend-swatch device" /> device node</span>
          <span className="legend-item"><span className="legend-swatch ring" /> active ring member</span>
        </div>
        <GraphView
          nodes={graphNodes}
          edges={graphEdges}
          ringDeviceIds={ringDeviceIds}
          ringUserIds={ringUserIds}
          onZoomControlReady={(controls) => {
            resetZoomRef.current = controls;
          }}
        />
      </div>
      <RingAlertsList ringAlerts={ringAlerts} />
    </section>
  );
}
