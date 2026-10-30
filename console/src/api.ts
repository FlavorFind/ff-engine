/**
 * Minimal typed API client for the Flavor Find engine.
 * Used only by the internal test console.
 *
 * Key and base are passed per-call so they can be set at runtime
 * (from localStorage or the header input) without a page reload.
 */

declare global {
  interface Window { __FF_API_KEY__?: string; __FF_API_BASE__?: string }
}

const BASE = import.meta.env.VITE_API_BASE
  ?? (typeof window !== "undefined" ? window.__FF_API_BASE__ : undefined)
  ?? "";

export const STORAGE_KEY = "ff_console_api_key";

/** Read the active API key: localStorage > window inject > env */
export function getStoredKey(): string {
  try { return localStorage.getItem(STORAGE_KEY) ?? ""; } catch { return ""; }
}

/** Persist the API key to localStorage */
export function saveKey(key: string): void {
  try { localStorage.setItem(STORAGE_KEY, key); } catch { /* ignore */ }
}

function headers(key: string) {
  return {
    "Content-Type": "application/json",
    ...(key ? { "X-API-Key": key } : {}),
  };
}

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

export interface DatasetVersion {
  engine_version: string;
  dataset_version: string;
  api_version: string;
}

// ── API calls ────────────────────────────────────────────────────────────────

export async function search(req: SearchRequest, key: string): Promise<SearchResponse> {
  const res = await fetch(`${BASE}/v1/search/by-ingredients`, {
    method: "POST",
    headers: headers(key),
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Search failed ${res.status}: ${text}`);
  }
  return res.json();
}

export async function getVersion(key: string): Promise<DatasetVersion> {
  const res = await fetch(`${BASE}/v1/meta/version`, { headers: headers(key) });
  if (!res.ok) throw new Error(`Version failed ${res.status}`);
  return res.json();
}
