import type {
  AxisPerformance,
  ModelMetrics,
  RingDetail,
  RingListResponse,
  SubgraphResponse,
  SweepResponse,
  TimelineResponse,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE}${path}`);
  if (!response.ok) {
    // Surface the server's own message where it has one; a bare status code
    // sends the reader to the network tab for no reason.
    let detail = response.statusText;
    try {
      detail = (await response.json()).detail ?? detail;
    } catch {
      /* body was not JSON */
    }
    throw new Error(`${response.status} ${detail}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => get<{ status: string; rings: number; clients: number }>("/health"),
  rings: (sort = "composite", limit = 120) =>
    get<RingListResponse>(`/rings?sort=${sort}&limit=${limit}`),
  ring: (id: number) => get<RingDetail>(`/rings/${id}`),
  subgraph: (id: number) => get<SubgraphResponse>(`/rings/${id}/subgraph`),
  timeline: (id: number) => get<TimelineResponse>(`/rings/${id}/events`),
  models: () => get<ModelMetrics>("/metrics/models"),
  axes: () => get<AxisPerformance>("/metrics/axes"),
  sweep: (model = "m1_tuned") => get<SweepResponse>(`/metrics/sweep?model=${model}&points=400`),
};

export const queryKeys = {
  rings: (sort: string) => ["rings", sort] as const,
  ring: (id: number) => ["ring", id] as const,
  subgraph: (id: number) => ["ring", id, "subgraph"] as const,
  timeline: (id: number) => ["ring", id, "timeline"] as const,
  models: () => ["metrics", "models"] as const,
  axes: () => ["metrics", "axes"] as const,
  sweep: (model: string) => ["metrics", "sweep", model] as const,
};
