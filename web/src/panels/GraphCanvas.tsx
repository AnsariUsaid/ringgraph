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
  // fcose runs asynchronously, so an in-flight layout has to be stopped
  // *before* the core it is laying out is destroyed. React tears effects down
  // in declaration order and the core is created in the first effect, so the
  // running layout has to be reachable from that effect's cleanup -- hence a
  // ref rather than a local.
  const layoutRef = useRef<cytoscape.Layouts | null>(null);

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
      // A five-node ring fitted to a 600px canvas lands at ~8x zoom, where the
      // nodes are dinner plates and the labels are headlines. Capping the zoom
      // means a small ring is drawn small -- which is also honest, since ring
      // size is one of the things being compared.
      maxZoom: 1.6,
      minZoom: 0.15,
      boxSelectionEnabled: false,
      textureOnViewport: true,
      hideEdgesOnViewport: true,
      motionBlur: false,
      style: [
        // Cytoscape's renderer cannot resolve CSS custom properties, so the
        // paper palette is duplicated here as literals. These must be kept in
        // step with tokens.css by hand -- there is no mechanism that does it.
        {
          selector: "node",
          style: {
            "background-color": "#8c91a0",
            width: 16,
            height: 16,
            "border-width": 1.5,
            "border-color": "#fffefb",
            label: "",
          },
        },
        {
          selector: 'node[kind = "Client"]',
          style: { "background-color": "#2f57d1", width: 20, height: 20, shape: "ellipse" },
        },
        {
          selector: 'node[kind = "Client"][?is_fraud]',
          style: {
            "background-color": "#b41d3c",
            // On paper a halo has to be drawn, not glowed: an outer ring in the
            // surface colour plus a wider one in the risk colour is the only
            // way to get the "advancing" read a dark theme gets for free.
            "border-width": 3,
            "border-color": "#f6d3da",
            width: 26,
            height: 26,
          },
        },
        { selector: 'node[kind = "DeviceInfo"]', style: { "background-color": "#8434c9", shape: "round-rectangle" } },
        { selector: 'node[kind = "id_33"]', style: { "background-color": "#0a8a82", shape: "diamond" } },
        { selector: 'node[kind = "id_30"]', style: { "background-color": "#ab6f17", shape: "round-triangle" } },
        { selector: 'node[kind = "id_31"]', style: { "background-color": "#2c874c", shape: "hexagon" } },
        {
          selector: "edge",
          style: {
            "line-color": "#a49b88",
            width: 1,
            // Higher than the dark theme's 0.45: a light edge on paper has far
            // less contrast to spend, so it has to be drawn nearer to solid.
            opacity: 0.55,
            "curve-style": "straight",
          },
        },
        {
          selector: 'edge[kind = "LINKED"]',
          style: { "line-color": "#3b2bd9", width: "mapData(weight, 1, 6, 1, 4)", opacity: 0.4 },
        },
        // Labels are the most expensive thing in Cytoscape's renderer, so they
        // appear only where they are being read.
        {
          selector: ".labelled",
          style: {
            label: "data(label)",
            "font-size": 9,
            "font-weight": 500,
            color: "#4c5364",
            // A halo behind the glyphs, because on paper a label crossing an
            // edge is genuinely hard to read and there is no dark field to
            // separate them.
            "text-outline-color": "#faf8f3",
            "text-outline-width": 2.5,
            "text-margin-y": -5,
            "min-zoomed-font-size": 8,
          },
        },
        { selector: ".dimmed", style: { opacity: 0.09 } },
        {
          selector: ".picked",
          style: { "border-width": 3, "border-color": "#3b2bd9", "overlay-opacity": 0 },
        },
        { selector: ".hovered", style: { "border-width": 3, "border-color": "#3b2bd9" } },
      ],
    });

    // Hover toggles a class directly and never touches React state: it fires on
    // mousemove, and a render per pixel would re-reconcile the whole canvas.
    cy.on("mouseover", "node", (event) => event.target.addClass("hovered"));
    cy.on("mouseout", "node", (event) => event.target.removeClass("hovered"));
    // Selection goes through React because a side panel renders from it; hover
    // does not, because it fires on mousemove. A tap on empty canvas clears it.
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
      layoutRef.current?.stop();
      layoutRef.current = null;
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
    layoutRef.current = layout;
    layout.run();
    return () => {
      // On a ring switch this runs while the core is alive and stops the old
      // layout. On unmount the mount effect's cleanup has already stopped it
      // and destroyed the core, and calling stop() again would throw.
      if (layoutRef.current !== layout) return;
      if (cyRef.current && !cyRef.current.destroyed()) layout.stop();
      layoutRef.current = null;
    };
  }, [data]);

  // Below the workbench breakpoint the columns stack and the page scrolls, so
  // a Cytoscape instance that swallows the wheel traps the reader on the
  // canvas with no way past it. Zoom and pan are handed back to the page
  // there; the graph stays a fitted figure, which is the right trade on a
  // screen that had no room to explore it anyway.
  useEffect(() => {
    const query = window.matchMedia("(min-width: 1121px)");
    const apply = () => {
      const cy = cyRef.current;
      if (!cy || cy.destroyed()) return;
      cy.userZoomingEnabled(query.matches);
      cy.userPanningEnabled(query.matches);
    };
    apply();
    query.addEventListener("change", apply);
    return () => query.removeEventListener("change", apply);
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
    <div style={{ position: "relative", height: "100%", background: "var(--paper-canvas)", minHeight: 0 }}>
      {/* The drafting grid sits under the graph, not behind the panel, so it
          pans with nothing and stays a backdrop rather than pretending to be
          a coordinate system. */}
      <div
        className="gridded"
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.6,
          maskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, #000 40%, transparent 100%)",
          WebkitMaskImage: "radial-gradient(ellipse 80% 80% at 50% 50%, #000 40%, transparent 100%)",
        }}
      />
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
        <>
          {/* Legend, because six shapes and six hues are not self-describing
              and the alternative is a reader guessing what a diamond is. */}
          <div
            style={{
              position: "absolute",
              left: 14,
              top: 14,
              display: "flex",
              flexWrap: "wrap",
              gap: 10,
              padding: "7px 11px",
              borderRadius: 999,
              background: "rgba(252, 250, 246, 0.82)",
              backdropFilter: "blur(10px)",
              WebkitBackdropFilter: "blur(10px)",
              border: "1px solid var(--rule)",
              boxShadow: "var(--lift-1)",
              pointerEvents: "none",
            }}
          >
            {[
              ["#2f57d1", "client"],
              ["#b41d3c", "fraud"],
              ["#8434c9", "device"],
              ["#0a8a82", "screen"],
              ["#ab6f17", "os"],
              ["#2c874c", "browser"],
            ].map(([colour, label]) => (
              <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 10.5, color: "var(--ink-2)" }}>
                <span style={{ width: 8, height: 8, borderRadius: 999, background: colour }} />
                {label}
              </span>
            ))}
          </div>

          <div
            className="mono"
            style={{
              position: "absolute",
              left: 14,
              bottom: 12,
              fontSize: 11,
              color: "var(--ink-3)",
              padding: "4px 10px",
              borderRadius: 999,
              background: "rgba(252, 250, 246, 0.82)",
              border: "1px solid var(--rule)",
              pointerEvents: "none",
            }}
          >
            {data.n_nodes} clients · {data.elements.length - data.n_nodes} links &amp; attributes · click a node for detail
          </div>
        </>
      )}
    </div>
  );
}
