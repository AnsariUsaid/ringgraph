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

export interface MeanSd {
  mean: number;
  sd: number;
}

export interface DelayedScores {
  "tpr_1pct": MeanSd;
  "tpr_0.1pct": MeanSd;
  n_seeds?: number;
  precision_1pct: MeanSd;
  frauds_caught_1pct: MeanSd;
  alerts_1pct: MeanSd;
}

export interface Difference {
  observed_difference: number;
  ci_low: number;
  ci_high: number;
  excludes_zero: boolean;
}

/** reports/headline.json, written by scripts/98_summary.py. */
export interface DelayedHeadline {
  causal: Record<
    string,
    {
      n_test: number;
      n_fraud: number;
      models: Record<string, DelayedScores>;
      comparisons: Record<string, Difference>;
      validation_tpr_1pct: Record<string, number>;
    }
  >;
  offline: {
    delay_days: number;
    levels: Record<string, DelayedScores & { pr_auc: MeanSd }>;
    comparisons: Record<string, Difference>;
  };
}

export interface ModelMetrics {
  structural: Record<string, StratumResult>;
  community: Record<string, StratumResult> | null;
  delayed?: DelayedHeadline | null;
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

export interface Summary {
  m1: { roc_auc: number; pr_auc: number; tpr_1pct: number; n_features: number };
  rings: {
    n_rings: number;
    n_ring_clients: number;
    n_ring_fraud_clients: number;
    ring_client_fraud_rate: number;
    base_client_fraud_rate: number;
    ring_txn_fraud_rate: number;
    base_txn_fraud_rate: number;
    rings_with_fraud: number;
    rings_multi_fraud: number;
    rings_all_fraud: number;
    rings_no_fraud: number;
    fraud_clients_in_multi_fraud_rings: number;
  };
}

export interface ShapExample {
  test_row: number;
  score: number;
  m1_score: number;
  top_features: { feature: string; family: string; shap: number }[];
}

export interface ShapReport {
  delay_days: number;
  flagged: number;
  frauds_caught: number;
  caught_only_by_graph: number;
  family_share_all_flagged: Record<string, number>;
  family_share_caught_only_by_graph: Record<string, number>;
  top_features_caught_only_by_graph: { feature: string; family: string; mean_abs_shap: number }[];
  examples: ShapExample[];
}
