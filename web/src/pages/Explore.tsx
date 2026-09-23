import { useState } from "react";
import { RingList } from "../panels/RingList";
import { GraphCanvas } from "../panels/GraphCanvas";
import { EvidencePanel } from "../panels/EvidencePanel";

/** The workbench: list, canvas, evidence.
 *
 * Unlike the other two routes this page does *not* scroll the window. It is a
 * fixed-height instrument with three independently scrolling columns, because
 * the whole point of the layout is that the canvas stays put while the list
 * beside it moves. Body scroll is suppressed for exactly as long as this route
 * is mounted.
 */
export function Explore() {
  // Opens on burst share, not on the composite. The composite is still
  // computed, still shown and still one click away -- its definition is
  // untouched. But it ranks at 1.27x against burst share's 1.72x, because two
  // of its four axes are anti-predictive, so defaulting to it would open the
  // tool on a ranking we have measured as the weaker one.
  const [sort, setSort] = useState("burst_share");

  return (
    <div className="workbench">
      <section className="card">
        <RingList sort={sort} onSortChange={setSort} />
      </section>

      <section className="card" style={{ position: "relative" }}>
        <GraphCanvas />
      </section>

      <section className="card">
        <EvidencePanel />
      </section>
    </div>
  );
}
