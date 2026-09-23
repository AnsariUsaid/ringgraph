import { create } from "zustand";

/** Client-side selection state.
 *
 * Deliberately small. Hover is *not* here: it fires on mousemove and is handled
 * inside Cytoscape as a class toggle, so it never causes a React render. The
 * threshold is local to the comparison panel for the same reason — dragging it
 * should not re-render the ring list (D-24, D-26).
 */
interface SelectionState {
  ringId: number | null;
  focusedAttribute: string | null;
  setRing: (id: number | null) => void;
  setFocusedAttribute: (id: string | null) => void;
}

export const useSelection = create<SelectionState>((set) => ({
  ringId: null,
  focusedAttribute: null,
  setRing: (ringId) => set({ ringId, focusedAttribute: null }),
  setFocusedAttribute: (focusedAttribute) => set({ focusedAttribute }),
}));
