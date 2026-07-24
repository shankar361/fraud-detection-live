import { useEffect, useRef } from "react";
import * as d3 from "d3";

const WIDTH = 720;
const HEIGHT = 380;

/**
 * Live force-directed graph of user<->device relationships.
 *
 * D3 owns this SVG subtree entirely and mutates it directly on each
 * simulation tick — this is the standard, performant pattern for
 * combining React with a force simulation, since a simulation can fire
 * dozens of ticks per second and funnelling every tick through React
 * state would be wasteful and janky.
 *
 * React's job is just to hand D3 new nodes/edges/ring-membership when
 * they change; two separate effects below handle "data changed, restart
 * the simulation" vs. "ring membership changed, just recolor" so a new
 * ring alert doesn't jolt the whole layout.
 */
export default function GraphView({ nodes, edges, ringDeviceIds, ringUserIds, onZoomControlReady }) {
  const svgRef = useRef(null);
  const containerRef = useRef(null);
  const tooltipRef = useRef(null);
  const stateRef = useRef(null); // holds simulation + selections, set up once
  const nodeMapRef = useRef(new Map()); // id -> persistent datum (keeps x/y stable across updates)

  // --- one-time setup: simulation, groups, zoom/pan ---
  useEffect(() => {
    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const g = svg.append("g");
    const linkGroup = g.append("g").attr("class", "graph-links");
    const nodeGroup = g.append("g").attr("class", "graph-nodes");

    const simulation = d3
      .forceSimulation()
      .force("link", d3.forceLink().id((d) => d.id).distance(65).strength(0.5))
      .force("charge", d3.forceManyBody().strength(-150))
      .force("center", d3.forceCenter(WIDTH / 2, HEIGHT / 2))
      .force("collide", d3.forceCollide(20));

    simulation.on("tick", () => {
      linkGroup
        .selectAll("line")
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);

      nodeGroup.selectAll("g.node").attr("transform", (d) => `translate(${d.x},${d.y})`);
    });

    const zoom = d3
      .zoom()
      .scaleExtent([0.4, 2.5])
      .on("zoom", (event) => g.attr("transform", event.transform));

    svg.call(zoom);

    const resetZoom = () => {
      svg.transition().duration(300).call(zoom.transform, d3.zoomIdentity);
    };

    if (typeof onZoomControlReady === "function") {
      onZoomControlReady({ reset: resetZoom });
    }

    stateRef.current = { simulation, linkGroup, nodeGroup, zoom };

    return () => {
      simulation.stop();
      if (typeof onZoomControlReady === "function") {
        onZoomControlReady(null);
      }
    };
  }, [onZoomControlReady]);

  // --- data changed: merge in new nodes/edges, restart the simulation ---
  useEffect(() => {
    const state = stateRef.current;
    if (!state) return;

    const { simulation, linkGroup, nodeGroup } = state;
    const nodeMap = nodeMapRef.current;

    const simNodes = nodes.map((n) => {
      let datum = nodeMap.get(n.id);
      if (!datum) {
        datum = {
          id: n.id,
          type: n.type,
          x: WIDTH / 2 + (Math.random() - 0.5) * 60,
          y: HEIGHT / 2 + (Math.random() - 0.5) * 60,
        };
        nodeMap.set(n.id, datum);
      }
      return datum;
    });

    const nodeIds = new Set(simNodes.map((node) => node.id));
    const simLinks = edges
      .filter((edge) => nodeIds.has(edge.source) && nodeIds.has(edge.target))
      .map((edge) => ({ source: edge.source, target: edge.target }));
    const connectedIds = new Set();
    simLinks.forEach((edge) => {
      connectedIds.add(edge.source);
      connectedIds.add(edge.target);
    });
    const connectedNodes = simNodes.filter((node) => connectedIds.has(node.id));

    simulation.nodes(connectedNodes);
    simulation.force("link").links(simLinks);
    simulation.alpha(0.6).restart();

    // links
    const link = linkGroup
      .selectAll("line")
      .data(simLinks, (d) => `${d.source.id || d.source}::${d.target.id || d.target}`);
    link.exit().remove();
    link.enter().append("line").attr("class", "graph-edge");

    // nodes
    const node = nodeGroup.selectAll("g.node").data(connectedNodes, (d) => d.id);
    node.exit().remove();

    const nodeEnter = node.enter().append("g").attr("class", "node");

    nodeEnter.each(function (d) {
      const sel = d3.select(this);
      if (d.type === "device") {
        sel.append("rect").attr("x", -8).attr("y", -8).attr("width", 16).attr("height", 16).attr("rx", 3);
      } else {
        sel.append("circle").attr("r", 7);
      }
      sel.append("title").text(d.id);
    })
    .on("mouseenter", function (event, d) {
      const tooltip = d3.select(tooltipRef.current);
      const containerRect = containerRef.current.getBoundingClientRect();
      tooltip
        .style("display", "block")
        .style("left", `${event.clientX - containerRect.left + 12}px`)
        .style("top", `${event.clientY - containerRect.top + 12}px`)
        .html(`<strong>${d.type.toUpperCase()}</strong><br/>${d.id}`);

      d3.select(this)
        .select(d.type === "device" ? "rect" : "circle")
        .attr("stroke", "#f59e0b")
        .attr("stroke-width", 3);
    })
    .on("mousemove", function (event) {
      const tooltip = d3.select(tooltipRef.current);
      const containerRect = containerRef.current.getBoundingClientRect();
      tooltip
        .style("left", `${event.clientX - containerRect.left + 12}px`)
        .style("top", `${event.clientY - containerRect.top + 12}px`);
    })
    .on("mouseleave", function (event, d) {
      d3.select(tooltipRef.current).style("display", "none");
      d3.select(this)
        .select(d.type === "device" ? "rect" : "circle")
        .attr("stroke", null)
        .attr("stroke-width", null);
    });

    applyRingStyling();
  }, [nodes, edges]);

  // --- ring membership changed: just recolor, don't restart the layout ---
  useEffect(() => {
    applyRingStyling();
  }, [ringDeviceIds, ringUserIds]);

  function applyRingStyling() {
    const state = stateRef.current;
    if (!state) return;
    const { nodeGroup, linkGroup } = state;

    nodeGroup.selectAll("g.node").each(function (d) {
      const isRing = ringDeviceIds.has(d.id) || ringUserIds.has(d.id);
      const shape = d3.select(this).select(d.type === "device" ? "rect" : "circle");
      shape.classed("ring-node", isRing);
    });

    linkGroup.selectAll("line").classed("ring-edge", (d) => {
      const a = d.source.id || d.source;
      const b = d.target.id || d.target;
      return (
        (ringDeviceIds.has(a) || ringUserIds.has(a)) &&
        (ringDeviceIds.has(b) || ringUserIds.has(b))
      );
    });
  }

  return (
    <div className="graph-container" ref={containerRef}>
      <div ref={tooltipRef} className="graph-tooltip" style={{ display: "none" }} />
      <svg
        ref={svgRef}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="graph-svg"
        role="img"
        aria-label="Live graph of users and devices, with fraud rings highlighted"
      />
    </div>
  );
}
