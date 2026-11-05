/**
 * Minimal typed API client for the Flavor Find engine.
 * Used only by the internal test console.
 */

declare global {
  interface Window { __FF_API_KEY__?: string; __FF_API_BASE__?: string }
}

// ── API base: injected by Django template via window.__FF_API_BASE__,
//    falling back to same-origin (empty string = relative URLs). ────────────────
const BASE =
  (typeof window !== "undefined" ? window.__FF_API_BASE__ : undefined) ?? "";

const KEY_STORAGE = "ff_console_api_key";

function getKey(): string {
  try {
    const stored = localStorage.getItem(KEY_STORAGE);
    if (stored) return stored;
  } catch {
    /* ignore */
  }
  // Fall back to key injected by the Django template.
  return (typeof window !== "undefined" ? window.__FF_API_KEY__ : undefined) ?? "";
}

export function getApiKey(): string {
  return getKey();
}

export function setApiKey(key: string): void {
  try {
    localStorage.setItem(KEY_STORAGE, key);
  } catch {
    /* ignore */
  }
}

export function hasApiKey(): boolean {
  return getKey() !== "";
}

/**
 * If the Django template injected an API key and the user hasn't set
 * one in localStorage, persist the injected key so it survives reloads.
 */
export function initKey(): void {
  const injected =
    (typeof window !== "undefined" ? window.__FF_API_KEY__ : undefined) ?? "";
  if (injected && !hasApiKey()) {
    setApiKey(injected);
  }
}

const headers = () => ({
  "Content-Type": "application/json",
  ...(getKey() ? { "X-API-Key": getKey() } : {}),
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

export interface IngredientRef {
  id: string;
  slug: string;
  name_en: string;
  name_sw: string;
}

export interface SearchResultItem {
  dish_id: string;
  slug: string;
  name_en: string;
  name_sw: string;
  score: number;
  tier: "exact" | "can_make" | "almost";
  matched: IngredientRef[];
  missing: IngredientRef[];
  unused: IngredientRef[];
  assumed_staples: IngredientRef[];
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
