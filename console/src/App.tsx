import { useEffect, useRef, useState } from "react";
import type {
  DatasetVersion,
  IngredientRef,
  SearchRequest,
  SearchResponse,
  SearchResultItem,
} from "./api";
import { getVersion, getStoredKey, saveKey, search } from "./api";

// ── Default weights matching the engine's config ──────────────────────────────
const DEFAULT_WEIGHTS: Record<string, number> = {
  coverage: 0.4,
  primary_hit: 0.2,
  usage_ratio: 0.15,
  popularity: 0.1,
  quality_bonus: 0.1,
  region_preference: 0.05,
  missing_penalty: -0.15,
};

// ── Small reusable components ─────────────────────────────────────────────────

function Badge({
  label,
  color,
}: {
  label: string;
  color: "green" | "yellow" | "orange" | "red" | "gray";
}) {
  const colors = {
    green: "bg-green-100 text-green-800",
    yellow: "bg-yellow-100 text-yellow-800",
    orange: "bg-orange-100 text-orange-800",
    red: "bg-red-100 text-red-800",
    gray: "bg-gray-100 text-gray-700",
  };
  return (
    <span
      className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${colors[color]}`}
    >
      {label}
    </span>
  );
}

function tierColor(tier: string): "green" | "yellow" | "orange" {
  if (tier === "exact") return "green";
  if (tier === "can_make") return "yellow";
  return "orange";
}

function ScoreBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(1, value)) * 100;
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 rounded bg-gray-200">
        <div
          className="h-1.5 rounded bg-indigo-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-gray-500">{value.toFixed(3)}</span>
    </div>
  );
}

function ResultCard({ item }: { item: SearchResultItem }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded border border-gray-200 bg-white p-3 shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="font-semibold text-gray-900">{item.name_en}</span>
          {item.name_sw && (
            <span className="ml-2 text-sm text-gray-500">/ {item.name_sw}</span>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Badge label={item.tier} color={tierColor(item.tier)} />
          <span className="text-sm font-mono text-indigo-600">
            {item.score.toFixed(3)}
          </span>
        </div>
      </div>

      {item.missing.length > 0 && (
        <div className="mt-1 text-xs text-red-600">
          Missing: {item.missing.map((i: IngredientRef) => i.name_en).join(", ")}
        </div>
      )}
      {item.unused.length > 0 && (
        <div className="mt-0.5 text-xs text-gray-400">
          Unused: {item.unused.map((i: IngredientRef) => i.name_en).join(", ")}
        </div>
      )}

      <button
        className="mt-2 text-xs text-indigo-500 hover:underline"
        onClick={() => setExpanded((e) => !e)}
      >
        {expanded ? "Hide breakdown" : "Show breakdown"}
      </button>

      {expanded && (
        <div className="mt-2 space-y-1 rounded bg-gray-50 p-2 text-xs">
          {Object.entries(item.score_breakdown ?? {}).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-4">
              <span className="w-36 text-gray-600">{k}</span>
              <ScoreBar value={v as number} />
            </div>
          ))}
          {item.assumed_staples.length > 0 && (
            <div className="text-gray-400">
              Staples assumed: {item.assumed_staples.map((i: any) => i.name_en).join(", ")}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function TierSection({
  title,
  items,
  color,
}: {
  title: string;
  items: SearchResultItem[];
  color: "green" | "yellow" | "orange";
}) {
  if (items.length === 0) return null;
  const headingColors = {
    green: "text-green-700",
    yellow: "text-yellow-700",
    orange: "text-orange-700",
  };
  return (
    <div>
      <h3 className={`mb-2 text-sm font-semibold ${headingColors[color]}`}>
        {title} ({items.length})
      </h3>
      <div className="space-y-2">
        {items.map((item) => (
          <ResultCard key={item.dish_id} item={item} />
        ))}
      </div>
    </div>
  );
}

// ── Weight editor ─────────────────────────────────────────────────────────────

function WeightEditor({
  weights,
  onChange,
}: {
  weights: Record<string, number>;
  onChange: (w: Record<string, number>) => void;
}) {
  return (
    <div className="space-y-1">
      {Object.entries(weights).map(([key, val]) => (
        <div key={key} className="flex items-center gap-3">
          <label className="w-40 text-xs text-gray-600">{key}</label>
          <input
            type="number"
            step="0.05"
            className="w-20 rounded border border-gray-200 px-2 py-0.5 text-xs"
            value={val}
            onChange={(e) =>
              onChange({ ...weights, [key]: parseFloat(e.target.value) || 0 })
            }
          />
        </div>
      ))}
    </div>
  );
}

// ── Resolved tokens panel ─────────────────────────────────────────────────────

function ResolvedPanel({ resp }: { resp: SearchResponse }) {
  if (!resp.resolved.length) return null;
  return (
    <div className="rounded border border-gray-200 bg-gray-50 p-3 text-xs">
      <div className="mb-1 font-semibold text-gray-700">Resolved inputs</div>
      <table className="w-full text-left">
        <thead>
          <tr className="text-gray-400">
            <th className="pr-3">Token</th>
            <th className="pr-3">Status</th>
            <th className="pr-3">Method</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {resp.resolved.map((r, i) => (
            <tr key={i} className="border-t border-gray-100">
              <td className="py-0.5 pr-3 font-mono">{r.token}</td>
              <td className="pr-3">
                <Badge
                  label={r.status}
                  color={
                    r.status === "matched"
                      ? "green"
                      : r.status === "ambiguous"
                        ? "yellow"
                        : "red"
                  }
                />
              </td>
              <td className="pr-3 text-gray-500">{r.method || "—"}</td>
              <td>{r.confidence.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {resp.unmatched.length > 0 && (
        <div className="mt-2 text-red-500">
          Unmatched: {resp.unmatched.join(", ")}
        </div>
      )}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────

export default function App() {
  const [apiKey, setApiKey] = useState(() => getStoredKey());
  const [keyInput, setKeyInput] = useState("");
  const [showKeyInput, setShowKeyInput] = useState(() => !getStoredKey());
  const [input, setInput] = useState("");
  const [mode, setMode] = useState<"strict" | "explore">("strict");
  const [limit, setLimit] = useState(20);
  const [weights, setWeights] = useState({ ...DEFAULT_WEIGHTS });
  const [compareWeights, setCompareWeights] = useState({ ...DEFAULT_WEIGHTS });
  const [compareMode, setCompareMode] = useState(false);

  const [result, setResult] = useState<SearchResponse | null>(null);
  const [resultB, setResultB] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);
  const [version, setVersion] = useState<DatasetVersion | null>(null);

  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!apiKey) return;
    getVersion(apiKey)
      .then(setVersion)
      .catch(() => {});
  }, [apiKey]);

  const runSearch = async () => {
    const ingredients = input
      .split(/[\n,]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    if (!ingredients.length) return;

    setLoading(true);
    setError(null);

    const req: SearchRequest = { ingredients, mode, limit, weights };
    const t0 = performance.now();

    try {
      const r = await search(req, apiKey);
      setElapsed(performance.now() - t0);
      setResult(r);

      if (compareMode) {
        const rB = await search({ ...req, weights: compareWeights }, apiKey);
        setResultB(rB);
      } else {
        setResultB(null);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) runSearch();
  };

  const totalA =
    (result?.results.exact.length ?? 0) +
    (result?.results.can_make.length ?? 0) +
    (result?.results.almost.length ?? 0);

  return (
    <div className="min-h-screen bg-gray-50 font-sans text-sm text-gray-800">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white px-6 py-3">
        <div className="flex items-center justify-between gap-4">
          <div className="shrink-0">
            <span className="text-base font-bold text-indigo-600">
              Flavor Find
            </span>
            <span className="ml-2 text-gray-400">Internal Test Console</span>
          </div>
          {/* API Key input */}
          <div className="flex flex-1 items-center gap-2 max-w-md">
            {showKeyInput ? (
              <>
                <input
                  type="text"
                  className="flex-1 rounded border border-gray-300 px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-indigo-400"
                  placeholder="Paste API key (ffk_…)" autoComplete="off" spellCheck={false}
                  value={keyInput}
                  onChange={(e) => setKeyInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && keyInput.trim()) {
                      saveKey(keyInput.trim());
                      setApiKey(keyInput.trim());
                      setShowKeyInput(false);
                      setKeyInput("");
                    }
                  }}
                />
                <button
                  className="rounded bg-indigo-600 px-3 py-1 text-xs text-white hover:bg-indigo-700 disabled:opacity-40"
                  disabled={!keyInput.trim()}
                  onClick={() => {
                    saveKey(keyInput.trim());
                    setApiKey(keyInput.trim());
                    setShowKeyInput(false);
                    setKeyInput("");
                  }}
                >
                  Save
                </button>
              </>
            ) : (
              <div className="flex items-center gap-2 text-xs text-gray-400">
                <span className="font-mono">{apiKey.slice(0, 12)}… ({apiKey.length})</span>
                <button
                  className="text-gray-400 hover:text-red-500"
                  title="Change key"
                  onClick={() => { saveKey(""); setApiKey(""); setShowKeyInput(true); }}
                >
                  ✕
                </button>
              </div>
            )}
          </div>
          {version && (
            <div className="shrink-0 text-xs text-gray-400">
              engine {version.engine_version} · dataset{" "}
              {version.dataset_version}
            </div>
          )}
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-6">
        <div className="grid grid-cols-[340px_1fr] gap-6">
          {/* ── Left panel — query form ─────────────────────────────────── */}
          <aside className="space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-600">
                Ingredients (one per line or comma-separated)
              </label>
              <textarea
                ref={inputRef}
                rows={5}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
                placeholder="tomato&#10;onion&#10;beans"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKey}
              />
            </div>

            <div className="flex gap-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">
                  Mode
                </label>
                <select
                  className="rounded border border-gray-300 px-2 py-1 text-xs"
                  value={mode}
                  onChange={(e) =>
                    setMode(e.target.value as "strict" | "explore")
                  }
                >
                  <option value="strict">strict</option>
                  <option value="explore">explore</option>
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-gray-600">
                  Limit
                </label>
                <input
                  type="number"
                  min={1}
                  max={50}
                  className="w-16 rounded border border-gray-300 px-2 py-1 text-xs"
                  value={limit}
                  onChange={(e) => setLimit(parseInt(e.target.value) || 20)}
                />
              </div>
            </div>

            <button
              onClick={runSearch}
              disabled={loading}
              className="w-full rounded bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {loading ? "Searching…" : "Search  ⌘↵"}
            </button>

            {error && (
              <div className="rounded bg-red-50 p-2 text-xs text-red-600">
                {error}
              </div>
            )}

            {/* Weights A */}
            <details>
              <summary className="cursor-pointer text-xs font-medium text-gray-600">
                Weights {compareMode ? "A" : ""}
              </summary>
              <div className="mt-2">
                <WeightEditor weights={weights} onChange={setWeights} />
                <button
                  className="mt-2 text-xs text-gray-400 hover:text-gray-600"
                  onClick={() => setWeights({ ...DEFAULT_WEIGHTS })}
                >
                  Reset to defaults
                </button>
              </div>
            </details>

            {/* Compare mode */}
            <label className="flex cursor-pointer items-center gap-2 text-xs text-gray-600">
              <input
                type="checkbox"
                checked={compareMode}
                onChange={(e) => setCompareMode(e.target.checked)}
              />
              Compare two weight sets side by side
            </label>

            {compareMode && (
              <details open>
                <summary className="cursor-pointer text-xs font-medium text-gray-600">
                  Weights B
                </summary>
                <div className="mt-2">
                  <WeightEditor
                    weights={compareWeights}
                    onChange={setCompareWeights}
                  />
                  <button
                    className="mt-2 text-xs text-gray-400 hover:text-gray-600"
                    onClick={() => setCompareWeights({ ...DEFAULT_WEIGHTS })}
                  >
                    Reset to defaults
                  </button>
                </div>
              </details>
            )}
          </aside>

          {/* ── Right panel — results ───────────────────────────────────── */}
          <main className="space-y-4">
            {result && (
              <>
                {/* Meta bar */}
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>
                    {totalA} result{totalA !== 1 ? "s" : ""}
                  </span>
                  <span>{result.candidate_count} candidates</span>
                  {elapsed !== null && (
                    <span className={elapsed > 300 ? "text-red-500" : ""}>
                      {elapsed.toFixed(0)} ms
                    </span>
                  )}
                  <span>v{result.dataset_version}</span>
                </div>

                <ResolvedPanel resp={result} />

                {compareMode && resultB ? (
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="mb-2 text-xs font-semibold text-indigo-600">
                        Weights A
                      </div>
                      <div className="space-y-4">
                        <TierSection
                          title="Exact"
                          items={result.results.exact}
                          color="green"
                        />
                        <TierSection
                          title="Can make"
                          items={result.results.can_make}
                          color="yellow"
                        />
                        <TierSection
                          title="Almost"
                          items={result.results.almost}
                          color="orange"
                        />
                      </div>
                    </div>
                    <div>
                      <div className="mb-2 text-xs font-semibold text-purple-600">
                        Weights B
                      </div>
                      <div className="space-y-4">
                        <TierSection
                          title="Exact"
                          items={resultB.results.exact}
                          color="green"
                        />
                        <TierSection
                          title="Can make"
                          items={resultB.results.can_make}
                          color="yellow"
                        />
                        <TierSection
                          title="Almost"
                          items={resultB.results.almost}
                          color="orange"
                        />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <TierSection
                      title="Exact"
                      items={result.results.exact}
                      color="green"
                    />
                    <TierSection
                      title="Can make"
                      items={result.results.can_make}
                      color="yellow"
                    />
                    <TierSection
                      title="Almost"
                      items={result.results.almost}
                      color="orange"
                    />
                  </div>
                )}
              </>
            )}

            {!result && !loading && (
              <div className="flex h-48 items-center justify-center text-gray-300">
                Enter ingredients and press Search
              </div>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}
