export type AxisName = "density" | "synchrony" | "concentration" | "tightness";

/** Fixed axis order. The risk signature glyph is readable as a *shape* only
 *  because this order never changes -- a ring flagged on synchrony looks
 *  different at 20px from one flagged on concentration (D-30). */
export const AXIS_ORDER: AxisName[] = ["density", "synchrony", "concentration", "tightness"];

export interface RingSummary {
  ring_id: number;
  n_clients: number;
  n_transactions: number;
  n_fraud_clients: number;
  fraud_share: number;
  composite: number;
  span_days: number;
  total_amount: number;
  axes: Record<AxisName, number>;
  raw: Record<AxisName, number>;
}

export interface RingListResponse {
  total: number;
  returned: number;
  sort: string;
  rings: RingSummary[];
}

export interface SharedAttribute {
  id: string;
  type: string;
  value: string;
  n_clients: number;
}

export interface RingMember {
  id: string;
  uid: string;
  n_transactions: number;
  total_amount: number;
  first_day: number;
  last_day: number;
  is_fraud: boolean;
}

export interface RingDetail extends RingSummary {
  first_day: number;
  last_day: number;
  burst_share: number;
  /** True total. `shared_attributes` below is capped by the API. */
  n_shared_attributes: number;
  shared_attributes: SharedAttribute[];
  members: RingMember[];
}

export interface CyElement {
  data: Record<string, string | number | boolean>;
}

export interface SubgraphResponse {
  ring_id: number;
  elements: CyElement[];
  n_nodes: number;
}

export interface TimelineEvent {
  t: number;
  day: number;
  amount: number;
  is_fraud: boolean;
}

export interface TimelineLane {
  id: string;
  uid: string;
  events: TimelineEvent[];
}

export interface TimelineResponse {
  ring_id: number;
  t_min: number;
  t_max: number;
  lanes: TimelineLane[];
}

export interface StratumResult {
  m1_mean: number;
  m1_sd: number;
  m2_mean: number;
  m2_sd: number;
  mean_diff: number;
  sd_diff: number;
  wins: number;
  n_seeds: number;
  per_seed_diffs: number[];
}

export interface ModelMetrics {
  structural: Record<string, StratumResult>;
  community: Record<string, StratumResult> | null;
  seed_note: string;
}

export interface AxisPerformance {
  client_fraud_rate: number;
  k: number;
  n_rings: number;
  /** Size-controlled: observed fraud clients over the number expected from
   *  ring size alone, so a ranking that only sorts by size scores 1.0. */
  axes: Record<
    string,
    { enrichment: number; observed_fraud_clients: number; expected_fraud_clients: number }
  >;
}

export interface SweepPoint {
  threshold: number;
  tp: number;
  fp: number;
  fn: number;
  tn: number;
  tpr: number;
  fpr: number;
  precision: number;
}

export interface SweepResponse {
  model: string;
  n: number;
  positives: number;
  sweep: SweepPoint[];
}
