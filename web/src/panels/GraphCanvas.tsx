import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import cytoscape, { type Core } from "cytoscape";
import fcose from "cytoscape-fcose";
import { api, queryKeys } from "../api/client";
import { StatePanel } from "../components/StatePanel";
import { useSelection } from "../store/selection";

cytoscape.use(fcose);

/** The only component that owns a Cytoscape instance.
 *
 * `cy` is never in React state, never in the store, never in a context other
 * components read: it is a rendering target, not a state container. Selection
 * and dimming are applied as stylesheet *classes* inside `cy.batch`, so a
 * selection change costs zero React reconciliation and zero relayout (D-26).
 */
export function GraphCanvas() {
  const ringId = useSelection((s) => s.ringId);
  const focusedAttribute = useSelection((s) => s.focusedAttribute);
  const selectedNodeId = useSelection((s) => s.selectedNodeId);
  const setSelectedNode = useSelection((s) => s.setSelectedNode);
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.subgraph(ringId ?? -1),
    queryFn: () => api.subgraph(ringId as number),
    enabled: ringId !== null,
  });

  useEffect(() => {
    if (!containerRef.current || cyRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      // Set at construction because most cannot change afterwards. The default
      // wheel sensitivity is uncomfortably fast on a trackpad and is an instant
      // "this feels cheap" tell.
      wheelSensitivity: 0.25,
      // A five-node ring fitted to a wide pane zooms so far that 9px labels
      // render larger than the nodes. Cap it; the user can still zoom in.
      maxZoom: 1.6,
      minZoom: 0.15,
      boxSelectionEnabled: false,
      textureOnViewport: true,
      hideEdgesOnViewport: true,
      motionBlur: false,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "var(--node-other)",
            width: 18,
            height: 18,
            "border-width": 0,
            label: "",
          },
        },
        {
          selector: 'node[kind = "Client"]',
          style: { "background-color": "#7aa7ff", width: 22, height: 22, shape: "ellipse" },
        },
        {
          selector: 'node[kind = "Client"][?is_fraud]',
          style: {
            "background-color": "#f04e4e",
            "border-width": 2,
            "border-color": "#ffd0d0",
            width: 26,
            height: 26,
          },
        },
        { selector: 'node[kind = "DeviceInfo"]', style: { "background-color": "#c77dff", shape: "round-rectangle" } },
        { selector: 'node[kind = "id_33"]', style: { "background-color": "#4fd1c5", shape: "diamond" } },
        { selector: 'node[kind = "id_30"]', style: { "background-color": "#f2b544", shape: "round-triangle" } },
        { selector: 'node[kind = "id_31"]', style: { "background-color": "#6fcf97", shape: "hexagon" } },
        {
          selector: "edge",
          style: {
            "line-color": "#3a4453",
            width: 1,
            opacity: 0.45,
            "curve-style": "straight",
          },
        },
        {
          selector: 'edge[kind = "LINKED"]',
          style: { "line-color": "#4c9aff", width: "mapData(weight, 1, 6, 1, 4)", opacity: 0.55 },
        },
        // Labels are the most expensive thing in Cytoscape's renderer, so they
        // appear only where they are being read.
        {
          selector: ".labelled",
          style: {
            label: "data(label)",
            "font-size": 9,
            color: "#9ba7b8",
            "text-margin-y": -4,
            "min-zoomed-font-size": 8,
          },
        },
        { selector: ".dimmed", style: { opacity: 0.12 } },
        {
          selector: ".picked",
          style: { "border-width": 3, "border-color": "#7fb8ff", "overlay-opacity": 0 },
        },
        { selector: ".hovered", style: { "border-width": 3, "border-color": "#7fb8ff" } },
      ],
    });

    // Hover toggles a class directly and never touches React state: it fires on
    // mousemove, and a render per pixel would re-reconcile the whole canvas.
    cy.on("mouseover", "node", (event) => event.target.addClass("hovered"));
    cy.on("mouseout", "node", (event) => event.target.removeClass("hovered"));
    // Selection goes through React because a side panel renders from it; hover
    // does not, because it fires on mousemove.
    cy.on("tap", "node", (event) => setSelectedNode(event.target.id()));
    cy.on("tap", (event) => {
      if (event.target === cy) setSelectedNode(null);
    });
    cyRef.current = cy;

    // A Cytoscape container inside a CSS grid reliably mounts at zero height,
    // which renders the graph invisible or crammed into a corner.
    const observer = new ResizeObserver(() => {
      cy.resize();
      if (cy.elements().length) cy.fit(cy.elements(), 40);
    });
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      cy.destroy();
      cyRef.current = null;
    };
  }, [setSelectedNode]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || !data) return;
    cy.batch(() => {
      cy.elements().remove();
      cy.add(data.elements as cytoscape.ElementDefinition[]);
      cy.nodes('[kind != "Client"]').addClass("labelled");
    });
    // fcose is asynchronous. Calling cy.fit() on the next line framed the
    // graph against randomised pre-layout positions, and the view only looked
    // right if the ResizeObserver happened to fire afterwards -- visible on
    // every ring selection. Fit on layoutstop instead, and stop the run on
    // cleanup so switching rings mid-layout cannot animate against removed
    // elements.
    const layout = cy.layout({
      name: "fcose",
      quality: "default",
      randomize: true,
      animate: data.elements.length < 300 ? "end" : false,
      nodeSeparation: 90,
      idealEdgeLength: 70,
    } as cytoscape.LayoutOptions);
    layout.one("layoutstop", () => cy.fit(cy.elements(), 40));
    layout.run();
    return () => {
      layout.stop();
    };
  }, [data]);

  // Selection is a class toggle inside cy.batch: no React reconciliation and no
  // relayout, which is the whole reason the canvas stays responsive.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("picked");
      if (selectedNodeId) cy.getElementById(selectedNodeId).addClass("picked");
    });
  }, [selectedNodeId, data]);

  // Attribute focus dims everything except that attribute's mediated edges.
  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.batch(() => {
      cy.elements().removeClass("dimmed");
      if (!focusedAttribute) return;
      const target = cy.getElementById(focusedAttribute);
      if (!target.length) return;
      const keep = target.closedNeighborhood();
      cy.elements().difference(keep).addClass("dimmed");
    });
  }, [focusedAttribute, data]);

  return (
    <div style={{ position: "relative", height: "100%", background: "var(--bg-canvas)", minHeight: 0 }}>
      <div ref={containerRef} style={{ position: "absolute", inset: 0 }} />
      {ringId === null && (
        <StatePanel
          title="Select a ring"
          body="Pick a candidate from the list to see the clients in it and the attributes that link them."
        />
      )}
      {ringId !== null && isError && <StatePanel title="Could not load this subgraph" tone="error" />}
      {ringId !== null && isLoading && (
        <StatePanel title="Extracting subgraph…" body="Building the client projection for this ring." />
      )}
      {data && (
        <div
          className="mono"
          style={{
            position: "absolute",
            left: 12,
            bottom: 10,
            fontSize: 11,
            color: "var(--fg-muted)",
            pointerEvents: "none",
          }}
        >
          {data.n_nodes} clients · {data.elements.length - data.n_nodes} links & attributes ·
          click a node for detail
        </div>
      )}
    </div>
  );
}
