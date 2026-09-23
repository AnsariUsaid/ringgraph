export type View = "overview" | "investigate" | "results";

export const VIEWS: { key: View; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "investigate", label: "Investigate" },
  { key: "results", label: "Results" },
];
