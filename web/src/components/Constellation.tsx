import { useEffect, useRef } from "react";

interface Node {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  /** Ring membership, or -1 for free-floating. */
  ring: number;
  /** Target position while captured by a ring. */
  tx: number;
  ty: number;
}

interface Ring {
  cx: number;
  cy: number;
  radius: number;
  born: number;
  /** Seconds the ring stays formed before it releases its members. */
  life: number;
}

const CAPTURE_MS = 600;
const LINK_DISTANCE = 124;

/** The hero's animated field: drifting clients that periodically condense into
 *  a coordinated ring, hold, pulse, and disperse.
 *
 * This is the product's actual claim rendered as motion -- fraud rings are not
 * visible as points, only as structure that appears over a window and then
 * dissolves. A generic particle-and-line background would say nothing; this
 * one says the thing the landing page is about, which is why it earns a canvas
 * instead of a static image.
 *
 * Canvas rather than SVG or DOM: at ~90 nodes with distance-tested edges this
 * is thousands of draw operations per frame, and that many SVG elements would
 * spend every frame in style recalculation.
 */
export function Constellation({ density = 1 }: { density?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Cytoscape's problem in miniature: a canvas cannot resolve CSS variables,
    // so the palette is read from the document once and cached.
    const css = getComputedStyle(document.documentElement);
    const ink = (name: string) => css.getPropertyValue(name).trim() || "#888";
    const COLORS = {
      node: ink("--node-client"),
      quiet: ink("--rule-ink"),
      edge: ink("--rule-ink"),
      ringEdge: ink("--accent"),
      risk: ink("--risk-4"),
      paper: ink("--paper"),
    };

    let width = 0;
    let height = 0;
    let dpr = 1;
    let nodes: Node[] = [];
    let rings: Ring[] = [];
    let frame = 0;
    let nextRingAt = 900;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

    function seed() {
      const count = Math.round(Math.min(125, Math.max(42, (width * height) / 12000)) * density);
      nodes = Array.from({ length: count }, () => ({
        x: Math.random() * width,
        y: Math.random() * height,
        vx: (Math.random() - 0.5) * 0.62,
        vy: (Math.random() - 0.5) * 0.62,
        r: 2.1 + Math.random() * 2.4,
        ring: -1,
        tx: 0,
        ty: 0,
      }));
      rings = [];
    }

    function resize() {
      const rect = canvas!.getBoundingClientRect();
      dpr = Math.min(2, window.devicePixelRatio || 1);
      width = rect.width;
      height = rect.height;
      canvas!.width = Math.round(width * dpr);
      canvas!.height = Math.round(height * dpr);
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      seed();
    }

    /** True where a formation will not land on the hero's headline.
     *
     * The first attempt at this excluded the whole centre column, which at
     * ~800px wide left no position satisfying both it and the in-bounds
     * clamp -- so no ring ever formed. Only the headline actually needs
     * protecting: it is the largest type on the page and the one thing a mesh
     * behind it genuinely spoils. The sub-copy and the stat row sit under the
     * scrim, and the stat cards are opaque paper, so a formation behind them
     * reads as depth rather than interference.
     *
     * Three regions qualify: above the headline, below it, and -- only on
     * viewports wide enough to have them -- the side margins. */
    function clearOfHeadline(x: number, y: number, radius: number, stage: number) {
      const above = y + radius < stage * 0.22;
      const below = y - radius > stage * 0.58;
      const beside = Math.abs(x - width / 2) > width * 0.34 + radius;
      return above || below || beside;
    }

    /** Capture the nodes nearest a random point into a circular formation. */
    function formRing(now: number) {
      if (!nodes.length) return;
      // Scaled to the viewport: a fixed 100px radius is a third of a phone's
      // width, where the ring would be more off-screen than on.
      // The hero is taller than the viewport on a phone, so the canvas runs
      // well below the fold. Formations are placed against the *visible*
      // height instead: otherwise the band under the headline lands off-screen
      // and roughly half of them are never seen.
      const stage = Math.min(height, window.innerHeight);
      const radius = Math.min(54 + Math.random() * 48, width * 0.17, stage * 0.22);

      let cx = 0;
      let cy = 0;
      let placed = false;
      for (let attempt = 0; attempt < 14 && !placed; attempt++) {
        cx = radius + 8 + Math.random() * Math.max(1, width - 2 * radius - 16);
        cy = radius + 8 + Math.random() * Math.max(1, stage - 2 * radius - 16);
        placed = clearOfHeadline(cx, cy, radius, stage);
      }
      // Very short viewports can still leave no clear band. Skipping is right:
      // the next tick tries again, and a hero with no room for a formation
      // should show drift rather than a ring over its own headline.
      if (!placed) return;

      const free = nodes.filter((n) => n.ring === -1);
      if (free.length < 12) return;

      const members = free
        .map((n) => ({ n, d: (n.x - cx) ** 2 + (n.y - cy) ** 2 }))
        .sort((a, b) => a.d - b.d)
        .slice(0, 6 + Math.floor(Math.random() * 4))
        .map((entry) => entry.n);

      const index = rings.length;
      members.forEach((node, i) => {
        const angle = (i / members.length) * Math.PI * 2 + Math.random() * 0.3;
        node.ring = index;
        node.tx = cx + Math.cos(angle) * radius;
        node.ty = cy + Math.sin(angle) * radius;
      });
      rings.push({ cx, cy, radius, born: now, life: 2400 + Math.random() * 1300 });
    }

    function step(now: number) {
      ctx!.clearRect(0, 0, width, height);

      if (now > nextRingAt && rings.length < 4) {
        formRing(now);
        nextRingAt = now + 1300 + Math.random() * 1100;
      }

      // Expire rings and release their members back into the drift with a
      // small outward impulse, so dispersal reads as release rather than a cut.
      rings = rings.filter((ring, index) => {
        if (now - ring.born < ring.life) return true;
        for (const node of nodes) {
          if (node.ring !== index) continue;
          node.ring = -1;
          const angle = Math.atan2(node.y - ring.cy, node.x - ring.cx);
          node.vx = Math.cos(angle) * 1.2;
          node.vy = Math.sin(angle) * 1.2;
        }
        return false;
      });
      // Indices shift when a ring is dropped, so members must be renumbered or
      // they would follow the wrong formation for the rest of their capture.
      const alive = new Map(rings.map((ring, i) => [ring, i]));
      for (const node of nodes) {
        if (node.ring === -1) continue;
        const ring = rings[node.ring];
        node.ring = ring ? (alive.get(ring) ?? -1) : -1;
      }

      for (const node of nodes) {
        if (node.ring === -1) {
          node.x += node.vx;
          node.y += node.vy;
          // Barely-damped, and re-energised whenever a node slows below the
          // threshold where drift stops reading as motion. The field has to be
          // visibly alive in the two seconds before the first ring forms.
          node.vx *= 0.999;
          node.vy *= 0.999;
          if (Math.abs(node.vx) < 0.18) node.vx += (Math.random() - 0.5) * 0.06;
          if (Math.abs(node.vy) < 0.18) node.vy += (Math.random() - 0.5) * 0.06;
          if (node.x < -20) node.x = width + 20;
          if (node.x > width + 20) node.x = -20;
          if (node.y < -20) node.y = height + 20;
          if (node.y > height + 20) node.y = -20;
        } else {
          // Critically-damped-ish pull toward the formation slot: fast at
          // first, no overshoot, which is what makes the snap feel deliberate.
          node.x += (node.tx - node.x) * 0.095;
          node.y += (node.ty - node.y) * 0.095;
        }
      }

      // Ambient links, drawn first so they sit under everything.
      ctx!.lineWidth = 1;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          if (a.ring !== -1 && a.ring === b.ring) continue;
          const dx = a.x - b.x;
          const dy = a.y - b.y;
          const d2 = dx * dx + dy * dy;
          if (d2 > LINK_DISTANCE * LINK_DISTANCE) continue;
          ctx!.globalAlpha = (1 - Math.sqrt(d2) / LINK_DISTANCE) * 0.5;
          ctx!.strokeStyle = COLORS.edge;
          ctx!.beginPath();
          ctx!.moveTo(a.x, a.y);
          ctx!.lineTo(b.x, b.y);
          ctx!.stroke();
        }
      }

      // Ring internals: every pair linked, which is exactly the density that
      // makes a ring a ring.
      rings.forEach((ring, index) => {
        const age = now - ring.born;
        const settle = Math.min(1, age / CAPTURE_MS);
        const fade = Math.min(1, (ring.life - age) / 600);
        const alpha = Math.max(0, Math.min(settle, fade));
        const members = nodes.filter((n) => n.ring === index);

        ctx!.strokeStyle = COLORS.ringEdge;
        ctx!.lineWidth = 2.4;
        for (let i = 0; i < members.length; i++) {
          for (let j = i + 1; j < members.length; j++) {
            ctx!.globalAlpha = alpha * 0.95;
            ctx!.beginPath();
            ctx!.moveTo(members[i].x, members[i].y);
            ctx!.lineTo(members[j].x, members[j].y);
            ctx!.stroke();
          }
        }

        // Halo: expands once per second while the ring is held.
        const beat = ((age % 1000) / 1000) ** 0.6;
        ctx!.globalAlpha = alpha * 0.75 * (1 - beat);
        ctx!.strokeStyle = COLORS.risk;
        ctx!.lineWidth = 3;
        ctx!.beginPath();
        ctx!.arc(ring.cx, ring.cy, ring.radius * (0.7 + beat * 0.85), 0, Math.PI * 2);
        ctx!.stroke();
      });

      for (const node of nodes) {
        const inRing = node.ring !== -1;
        ctx!.globalAlpha = inRing ? 1 : 0.7;
        ctx!.fillStyle = inRing ? COLORS.risk : COLORS.node;
        ctx!.beginPath();
        ctx!.arc(node.x, node.y, inRing ? node.r + 3 : node.r, 0, Math.PI * 2);
        ctx!.fill();
        if (inRing) {
          ctx!.strokeStyle = COLORS.paper;
          ctx!.lineWidth = 2;
          ctx!.stroke();
        }
      }

      ctx!.globalAlpha = 1;
      frame = requestAnimationFrame(step);
    }

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(canvas);

    if (reduced.matches) {
      // One frame: the structure is still legible, nothing moves.
      formRing(0);
      for (let i = 0; i < 90; i++) {
        for (const node of nodes) {
          if (node.ring === -1) continue;
          node.x += (node.tx - node.x) * 0.2;
          node.y += (node.ty - node.y) * 0.2;
        }
      }
      cancelAnimationFrame(frame);
      step(400);
      cancelAnimationFrame(frame);
    } else {
      frame = requestAnimationFrame(step);
    }

    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [density]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", display: "block" }}
    />
  );
}
