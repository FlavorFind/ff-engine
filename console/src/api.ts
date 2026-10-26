/**
 * Minimal typed API client for the Flavor Find engine.
 * Used only by the internal test console.
 */

const BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";
const KEY = import.meta.env.VITE_API_KEY ?? "";

const headers = () => ({
  "Content-Type": "application/json",
  ...(KEY ? { "X-API-Key": KEY } : {}),
});

// ── Types ────────────────────────────────────────────────────────────────────

export interface ResolvedToken {
  token: string;
  status: "matched" | "ambiguous" | "unmatched";
  ingredient_id: string | null;
  method: string;
  confidence: number;
}

export interface ScoreBreakdown {
  coverage: number;
  primary_hit: number;
  usage_ratio: number;
  popularity: number;
  quality_bonus: number;
  region_preference: number;
  missing_penalty: number;
}

export interface SearchResultItem {
  dish_id: string;
  slug: string;
  name_en: string;
  name_sw: string;
  score: number;
  tier: "exact" | "can_make" | "almost";
  matched: string[];
  missing: string[];
  unused: string[];
  assumed_staples: string[];
  score_breakdown: ScoreBreakdown;
}

export interface SearchResponse {
  dataset_version: string;
  mode: string;
  candidate_count: number;
  total_results: number;
  resolved: ResolvedToken[];
  ambiguous: string[];
  unmatched: string[];
  results: {
    exact: SearchResultItem[];
    can_make: SearchResultItem[];
    almost: SearchResultItem[];
  };
}

export interface SearchRequest {
  ingredients: string[];
  mode: "strict" | "explore";
  limit: number;
  meal_type?: string;
  course?: string;
  diet?: string[];
  weights?: Record<string, number>;
}

export interface ZeroResultQuery {
  id: number;
  raw_input: string;
  normalised_input: string;
  count: number;
  last_seen: string;
}

// ── API calls ────────────────────────────────────────────────────────────────

export async function search(req: SearchRequest): Promise<SearchResponse> {
  const res = await fetch(`${BASE}/v1/search/by-ingredients`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Search failed ${res.status}: ${text}`);
  }
  return res.json();
}

export interface DatasetVersion {
  engine_version: string;
  dataset_version: string;
  api_version: string;
}

export async function getVersion(): Promise<DatasetVersion> {
  const res = await fetch(`${BASE}/v1/meta/version`, { headers: headers() });
  if (!res.ok) throw new Error(`Version failed ${res.status}`);
  return res.json();
}
