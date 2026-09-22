import { create } from "zustand";

/** Client-side selection state.
 *
 * Hover lives here rather than in React state because it changes on mousemove:
 * routing it through a render would re-reconcile the canvas on every pixel.
 * The Cytoscape handler toggles a class directly *and* writes here, so the side
 * panels can follow without the canvas paying for it (D-24, D-26).
 */
interface SelectionState {
  ringId: number | null;
  hoveredId: string | null;
  focusedAttribute: string | null;
  threshold: number;
  setRing: (id: number | null) => void;
  setHovered: (id: string | null) => void;
  setFocusedAttribute: (id: string | null) => void;
  setThreshold: (value: number) => void;
}

export const useSelection = create<SelectionState>((set) => ({
  ringId: null,
  hoveredId: null,
  focusedAttribute: null,
  threshold: 0.5,
  setRing: (ringId) => set({ ringId, focusedAttribute: null }),
  setHovered: (hoveredId) => set({ hoveredId }),
  setFocusedAttribute: (focusedAttribute) => set({ focusedAttribute }),
  setThreshold: (threshold) => set({ threshold }),
}));
