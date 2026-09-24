import { create } from "zustand";

/** Client-side selection state.
 *
 * Deliberately small. Hover is *not* here: it fires on mousemove and is handled
 * inside Cytoscape as a class toggle, so it never causes a React render. The
 * threshold is local to the results view for the same reason (D-24, D-26).
 */
interface SelectionState {
  ringId: number | null;
  /** Namespaced node id from the canvas, e.g. `client:7f3a` or
   *  `attr:DeviceInfo:Windows`. Drives the detail card in the evidence panel. */
  selectedNodeId: string | null;
  focusedAttribute: string | null;
  setRing: (id: number | null) => void;
  setSelectedNode: (id: string | null) => void;
  setFocusedAttribute: (id: string | null) => void;
}

export const useSelection = create<SelectionState>((set) => ({
  ringId: null,
  selectedNodeId: null,
  focusedAttribute: null,
  // Changing ring invalidates any node selection made inside the old one.
  setRing: (ringId) => set({ ringId, focusedAttribute: null, selectedNodeId: null }),
  setSelectedNode: (selectedNodeId) => set({ selectedNodeId }),
  setFocusedAttribute: (focusedAttribute) => set({ focusedAttribute }),
}));
