#!/usr/bin/env python3
"""
FF-Engine Search Quality Probe
================================
Tests the engine's search results with combinations of the 20 most common
East African cooking ingredients. Queries run in groups of 1–8 ingredients
and results are printed cleanly to the terminal.

Usage:
    python probe_search.py

Config (edit or set as env vars):
    ENGINE_URL   — default: http://localhost:8001
    ENGINE_KEY   — default: ffk_6342e74c59c5bf955b650605a003ba3c378c09d5
    MODE         — "explore" shows "almost" tier too (default), "strict" hides it
    LIMIT        — max results per tier (default: 5)
"""

import itertools
import json
import os
import sys
import textwrap
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

ENGINE_URL = os.environ.get("ENGINE_URL", "http://localhost:8001").rstrip("/")
ENGINE_KEY = os.environ.get(
    "ENGINE_KEY",
    "ffk_6342e74c59c5bf955b650605a003ba3c378c09d5",
)
MODE = os.environ.get("MODE", "explore")       # explore | strict
LIMIT = int(os.environ.get("LIMIT", "5"))      # results per tier
TIMEOUT = int(os.environ.get("TIMEOUT", "15")) # HTTP timeout seconds

# Output file — written alongside this script
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
RESULTS_DIR = Path(__file__).parent / "probe_results"
RESULTS_DIR.mkdir(exist_ok=True)
RESULTS_FILE = RESULTS_DIR / f"probe_{TIMESTAMP}.txt"

# ─────────────────────────────────────────────────────────────────────────────
# THE 20 INGREDIENTS (most common East African kitchen staples + fresh produce)
# ─────────────────────────────────────────────────────────────────────────────

INGREDIENTS = [
    "onions",
    "tomatoes",
    "garlic",
    "ginger",
    "sukuma wiki",
    "pilipili hoho",
    "coconut milk",
    "beef",
    "chicken",
    "rice",
    "maize flour",
    "lentils",
    "spinach",
    "carrots",
    "cabbage",
    "potatoes",
    "eggs",
    "tomato paste",
    "coriander",
    "green pepper",
]

# Combo sizes to test: groups of 1, 2, 3, 4, 5, 6, 7, 8
COMBO_SIZES = [1, 2, 3, 4, 5, 6, 7, 8]

# ─────────────────────────────────────────────────────────────────────────────
# DUAL OUTPUT — terminal (with colour) + file (plain text)
# ─────────────────────────────────────────────────────────────────────────────

_ANSI_RE = __import__("re").compile(r"\033\[[0-9;]*m")
_outfile = None  # opened in main()

def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)

def out(text: str = ""):
    """Print to terminal AND append plain text to the results file."""
    print(text)
    if _outfile:
        _outfile.write(_strip_ansi(text) + "\n")
        _outfile.flush()


USE_COLOUR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if USE_COLOUR else text

def bold(t):    return _c("1", t)
def dim(t):     return _c("2", t)
def green(t):   return _c("32", t)
def yellow(t):  return _c("33", t)
def cyan(t):    return _c("36", t)
def red(t):     return _c("31", t)
def magenta(t): return _c("35", t)
def blue(t):    return _c("34", t)

TIER_COLOUR = {
    "exact":    green,
    "can_make": cyan,
    "almost":   yellow,
}
TIER_LABEL = {
    "exact":    "EXACT   ",
    "can_make": "CAN MAKE",
    "almost":   "ALMOST  ",
}

# ─────────────────────────────────────────────────────────────────────────────
# HTTP CLIENT
# ─────────────────────────────────────────────────────────────────────────────

def search(ingredients: list[str]) -> dict:
    """POST to /v1/search/by-ingredients and return the parsed JSON."""
    payload = json.dumps({
        "ingredients": ingredients,
        "mode": MODE,
        "limit": LIMIT,
    }).encode()

    req = urllib.request.Request(
        url=f"{ENGINE_URL}/v1/search/by-ingredients",
        data=payload,
        headers={
            "X-API-Key": ENGINE_KEY,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ff-probe/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        return {"_error": f"HTTP {e.code}", "_body": body}
    except Exception as exc:
        return {"_error": str(exc)}

# ─────────────────────────────────────────────────────────────────────────────
# DISPLAY HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def score_bar(score: float, width: int = 20) -> str:
    """Visual bar representing a 0–1 score."""
    filled = round(score * width)
    bar = "█" * filled + "░" * (width - filled)
    return bar

def fmt_inglist(refs: list[dict], colour_fn=None) -> str:
    """Format a list of ingredient refs as a compact comma string."""
    if not refs:
        return dim("—")
    names = [r.get("name_en") or r.get("slug", "?") for r in refs]
    text = ", ".join(names)
    return colour_fn(text) if colour_fn else text

def print_separator(char="─", width=80):
    out(dim(char * width))

def print_header(text: str):
    out()
    out(bold(cyan(f"  {text}")))
    print_separator("═")

def print_dish(rank: int, dish: dict):
    """Print one dish result with tier, score, matched/missing/unused."""
    tier = dish.get("tier", "?")
    name = dish.get("name_en", dish.get("slug", "?"))
    name_sw = dish.get("name_sw", "")
    score = dish.get("score", 0.0)
    quality = dish.get("quality_level", "?")

    matched = dish.get("matched", [])
    missing = dish.get("missing", [])
    unused  = dish.get("unused", [])
    staples = dish.get("assumed_staples", [])
    breakdown = dish.get("score_breakdown", {})

    tier_fn   = TIER_COLOUR.get(tier, lambda x: x)
    tier_label = TIER_LABEL.get(tier, tier.upper().ljust(8))

    # Line 1 — rank, tier badge, name, score bar
    bar = score_bar(score)
    sw_hint = f"  {dim(name_sw)}" if name_sw else ""
    out(
        f"  {dim(str(rank).rjust(2))}.  "
        f"{tier_fn(bold(tier_label))}  "
        f"{bold(name)}{sw_hint}  "
        f"{tier_fn(bar)}  {bold(f'{score:.3f}')}"
        f"  {dim(f'[{quality}]')}"
    )

    # Line 2 — ingredient breakdown
    matched_str = fmt_inglist(matched, green)
    missing_str = fmt_inglist(missing, red)
    unused_str  = fmt_inglist(unused, yellow)
    staples_str = fmt_inglist(staples, dim)

    out(f"       {dim('matched:')} {matched_str}")

    if missing:
        out(f"       {dim('missing:')} {missing_str}")
    if unused:
        out(f"       {dim('unused :')} {unused_str}")
    if staples:
        out(f"       {dim('staples:')} {staples_str}")

    # Line 3 — score breakdown (compact)
    bd_parts = []
    for k, v in breakdown.items():
        if k == "total":
            continue
        if abs(v) > 0.0001:
            colour = red if v < 0 else dim
            bd_parts.append(colour(f"{k}={v:+.3f}"))
    if bd_parts:
        out(f"       {dim('score  :')} {dim('  '.join(bd_parts))}")

    out()

def print_resolution(resolved: list, ambiguous: list, unmatched: list):
    """Show how the engine understood each input token."""
    parts = []
    for r in resolved:
        tok = r.get("token", "?")
        status = r.get("status", "?")
        method = r.get("method", "")
        conf   = r.get("confidence", 0.0)
        if status == "matched":
            parts.append(green(f"✓ {tok}") + dim(f" ({method} {conf:.0%})"))
        elif status == "ambiguous":
            parts.append(yellow(f"? {tok}") + dim(" (ambiguous)"))
        else:
            parts.append(red(f"✗ {tok}") + dim(" (unmatched)"))
    for a in ambiguous:
        parts.append(yellow(f"? {a}") + dim(" (ambiguous)"))
    for u in unmatched:
        parts.append(red(f"✗ {u}") + dim(" (unmatched)"))

    out("  " + "   ".join(parts))

# ─────────────────────────────────────────────────────────────────────────────
# COMBO GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def build_combos() -> list[list[str]]:
    """
    For each combo size N (1–8), pick a representative sample of combinations
    so we don't spam hundreds of requests.

    Strategy:
      N=1 : every single ingredient (20 combos — the most important for quality check)
      N=2 : the first 10 pairs (sequential neighbours in the list)
      N=3 : first 8 triples
      N=4 : first 6 quads
      N=5 : first 4 sets of 5
      N=6 : first 3 sets of 6
      N=7 : first 2 sets of 7
      N=8 : 1 set of 8 (the first 8 ingredients)
    """
    limits = {1: 20, 2: 10, 3: 8, 4: 6, 5: 4, 6: 3, 7: 2, 8: 1}
    combos: list[list[str]] = []

    for size in COMBO_SIZES:
        count = 0
        cap   = limits[size]
        for combo in itertools.combinations(INGREDIENTS, size):
            combos.append(list(combo))
            count += 1
            if count >= cap:
                break

    return combos

# ─────────────────────────────────────────────────────────────────────────────
# VERDICT HELPERS — the quality analysis you care about
# ─────────────────────────────────────────────────────────────────────────────

def analyse_quality(ingredients: list[str], result: dict) -> list[str]:
    """
    Return a list of observations about whether the results make sense.
    This is the 'opinion' layer — flags things that look wrong or right.
    """
    notes = []
    tiers = result.get("results", {})
    exact    = tiers.get("exact", [])
    can_make = tiers.get("can_make", [])
    almost   = tiers.get("almost", [])
    all_results = exact + can_make + almost

    total = result.get("total_results", 0)
    unmatched = result.get("unmatched", [])

    # ── Single ingredient edge case ──────────────────────────────────────────
    if len(ingredients) == 1:
        ing = ingredients[0].lower()
        if total == 0:
            notes.append(red("✗ ZERO RESULTS") + dim(" — engine returned nothing for a single ingredient"))
        else:
            # Check if exact results exist — for single non-staple ingredient,
            # exact means the dish needs ONLY that ingredient (+ staples).
            # This is rare. If it exists it should be verified.
            if exact:
                exact_names = [d.get("name_en","?") for d in exact[:3]]
                notes.append(green("✓ EXACT hits for single ingredient: ") + bold(", ".join(exact_names)))
                notes.append(dim("  → These dishes need only this ingredient + kitchen staples (salt/oil/water)"))
            if can_make:
                cm_names = [d.get("name_en","?") for d in can_make[:3]]
                notes.append(cyan("✓ CAN MAKE hits: ") + bold(", ".join(cm_names)))
                notes.append(dim("  → You have all required ingredients because the rest are staples"))
            if almost and not exact and not can_make:
                al_names = [d.get("name_en","?") for d in almost[:3]]
                notes.append(yellow("△ ONLY ALMOST results: ") + bold(", ".join(al_names)))
                notes.append(dim(f"  → Closest matches — missing 1 non-staple ingredient"))

        # Check order — first result should be highest scorer
        if len(all_results) >= 2:
            scores = [d.get("score", 0) for d in all_results]
            if scores != sorted(scores, reverse=True):
                notes.append(red("✗ ORDER BUG — results are NOT sorted by score descending"))
            else:
                notes.append(green("✓ ORDER OK — sorted highest score first within tiers"))

    # ── Multi ingredient ─────────────────────────────────────────────────────
    else:
        if total == 0:
            notes.append(red("✗ ZERO RESULTS") + dim(f" — no dishes found for {len(ingredients)} ingredients"))
        elif total < 3:
            notes.append(yellow(f"△ LOW RESULTS ({total})") + dim(" — only a few dishes matched"))
        else:
            notes.append(green(f"✓ {total} total results") + dim(f" ({len(exact)} exact, {len(can_make)} can_make, {len(almost)} almost)"))

        # Check that more ingredients = more exact results (generally)
        if len(ingredients) >= 4 and not exact and not can_make:
            notes.append(yellow("△ No exact/can_make results with 4+ ingredients — data may be thin"))

        # Top result sanity
        if all_results:
            top = all_results[0]
            top_name = top.get("name_en","?")
            top_score = top.get("score", 0)
            top_tier = top.get("tier","?")
            notes.append(dim(f"  Top: {bold(top_name)} ({TIER_LABEL.get(top_tier, top_tier).strip()}, score={top_score:.3f})"))

    # ── Unmatched tokens ─────────────────────────────────────────────────────
    if unmatched:
        notes.append(yellow(f"△ UNMATCHED tokens: ") + red(", ".join(unmatched)))
        notes.append(dim("  → These words are not in the ingredient dictionary — add aliases"))

    return notes

# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY COLLECTOR
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ComboResult:
    ingredients: list[str]
    size: int
    total: int
    exact: int
    can_make: int
    almost: int
    unmatched: list[str]
    top_name: str
    top_score: float
    top_tier: str
    error: str = ""

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    global _outfile
    combos = build_combos()

    # Open results file
    _outfile = open(RESULTS_FILE, "w", encoding="utf-8")
    _outfile.write(f"FF-Engine Search Quality Probe\n")
    _outfile.write(f"Run at : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    _outfile.write(f"Engine : {ENGINE_URL}\n")
    _outfile.write(f"Mode   : {MODE}\n")
    _outfile.write("=" * 80 + "\n\n")

    # ── Banner ────────────────────────────────────────────────────────────────
    out()
    out(bold(cyan("╔══════════════════════════════════════════════════════════════════╗")))
    out(bold(cyan("║         FF-ENGINE  SEARCH QUALITY PROBE                         ║")))
    out(bold(cyan("╚══════════════════════════════════════════════════════════════════╝")))
    out()
    out(f"  Engine : {bold(ENGINE_URL)}")
    out(f"  Mode   : {bold(MODE)}")
    out(f"  Limit  : {bold(str(LIMIT))} results per tier")
    out(f"  Combos : {bold(str(len(combos)))} queries  "
          f"({', '.join(f'{COMBO_SIZES[i]}x{[1,10,8,6,4,3,2,1][i]}' for i in range(len(COMBO_SIZES)))})")
    out()
    out(f"  Ingredients under test ({len(INGREDIENTS)}):")
    cols = 4
    for i in range(0, len(INGREDIENTS), cols):
        row = INGREDIENTS[i:i+cols]
        out("    " + "  ".join(f"{dim(str(i+j+1).rjust(2))}. {r:<18}" for j, r in enumerate(row)))
    out()
    print_separator("═")

    # ── Health check ──────────────────────────────────────────────────────────
    try:
        req = urllib.request.Request(
            f"{ENGINE_URL}/v1/health/",
            headers={
                "X-API-Key": ENGINE_KEY,
                "User-Agent": "ff-probe/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            health = json.loads(resp.read())
        db_status = health.get("database", "?")
        out(f"\n  {green('● Engine is UP')}  database={bold(db_status)}\n")
    except Exception as exc:
        out(f"\n  {red('✗ Engine is DOWN:')} {exc}\n")
        out(f"  Make sure the engine is running at {ENGINE_URL}")
        out(f"  and your key is valid.\n")
        sys.exit(1)

    # ── Run combos ────────────────────────────────────────────────────────────
    summary: list[ComboResult] = []
    total_queries = len(combos)
    current_size = None

    for idx, ings in enumerate(combos, 1):
        size = len(ings)

        # Print group header when size changes
        if size != current_size:
            current_size = size
            size_label = {
                1: "SINGLE INGREDIENT  (the key quality test)",
                2: "2-INGREDIENT COMBOS",
                3: "3-INGREDIENT COMBOS",
                4: "4-INGREDIENT COMBOS",
                5: "5-INGREDIENT COMBOS",
                6: "6-INGREDIENT COMBOS",
                7: "7-INGREDIENT COMBOS",
                8: "8-INGREDIENT COMBOS",
            }.get(size, f"{size}-INGREDIENT COMBOS")
            print_header(f"GROUP: {size_label}")

        # ── Query label ───────────────────────────────────────────────────────
        ing_label = " + ".join(bold(i) for i in ings)
        out(f"  [{dim(str(idx).rjust(3))}/{dim(str(total_queries))}]  {ing_label}")
        print_separator("·")

        # ── Call engine ───────────────────────────────────────────────────────
        t0 = time.time()
        result = search(ings)
        elapsed = time.time() - t0

        # ── Error guard ───────────────────────────────────────────────────────
        if "_error" in result:
            out(f"  {red('ERROR:')} {result['_error']}")
            if "_body" in result:
                out(f"  {dim(result['_body'][:200])}")
            out()
            summary.append(ComboResult(
                ingredients=ings, size=size,
                total=0, exact=0, can_make=0, almost=0,
                unmatched=[], top_name="", top_score=0, top_tier="",
                error=result["_error"],
            ))
            continue

        # ── Parse result ──────────────────────────────────────────────────────
        tiers       = result.get("results", {})
        exact_list  = tiers.get("exact", [])
        cm_list     = tiers.get("can_make", [])
        almost_list = tiers.get("almost", [])
        all_dishes  = exact_list + cm_list + almost_list
        total       = result.get("total_results", 0)
        candidates  = result.get("candidate_count", 0)
        resolved    = result.get("resolved", [])
        ambiguous   = result.get("ambiguous", [])
        unmatched   = result.get("unmatched", [])

        # ── Resolution row ────────────────────────────────────────────────────
        print_resolution(resolved, ambiguous, unmatched)
        out()

        # ── Stats line ────────────────────────────────────────────────────────
        tier_summary = (
            f"{green(str(len(exact_list)))} exact  "
            f"{cyan(str(len(cm_list)))} can_make  "
            f"{yellow(str(len(almost_list)))} almost"
        )
        out(f"  {dim('candidates:')} {candidates}   "
              f"{dim('results:')} {bold(str(total))}   "
              f"{tier_summary}   "
              f"{dim(f'{elapsed*1000:.0f}ms')}")
        out()

        # ── Quality verdict ───────────────────────────────────────────────────
        notes = analyse_quality(ings, result)
        for note in notes:
            out(f"  {note}")
        if notes:
            out()

        # ── Print dishes (up to LIMIT per tier, all tiers merged in order) ───
        if not all_dishes:
            out(f"  {red('No dishes returned.')}")
            if size == 1:
                out(f"  {dim('→ The ingredient may not match any dish in the database.')}")
                out(f"  {dim('→ Check the unmatched list above and add aliases.')}")
        else:
            rank = 1
            for tier_key, tier_list in [
                ("exact",    exact_list),
                ("can_make", cm_list),
                ("almost",   almost_list),
            ]:
                if tier_list:
                    for dish in tier_list:
                        print_dish(rank, dish)
                        rank += 1

        # ── Summary record ────────────────────────────────────────────────────
        top = all_dishes[0] if all_dishes else {}
        summary.append(ComboResult(
            ingredients=ings,
            size=size,
            total=total,
            exact=len(exact_list),
            can_make=len(cm_list),
            almost=len(almost_list),
            unmatched=unmatched,
            top_name=top.get("name_en", ""),
            top_score=top.get("score", 0),
            top_tier=top.get("tier", ""),
        ))

        # small pause to avoid hammering
        time.sleep(0.05)

    # ─────────────────────────────────────────────────────────────────────────
    # FINAL SUMMARY TABLE
    # ─────────────────────────────────────────────────────────────────────────
    out()
    out(bold(cyan("╔══════════════════════════════════════════════════════════════════╗")))
    out(bold(cyan("║                       SUMMARY                                   ║")))
    out(bold(cyan("╚══════════════════════════════════════════════════════════════════╝")))
    out()

    # Stats by group size
    out(bold("  Results by group size:"))
    out()
    out(f"  {'Size':<6} {'Queries':<8} {'Avg Total':<10} {'Exact%':<8} {'CanMake%':<10} {'Almost%':<8} {'ZeroRes':<8}")
    print_separator()

    for size in COMBO_SIZES:
        rows = [r for r in summary if r.size == size and not r.error]
        if not rows:
            continue
        n = len(rows)
        avg_total   = sum(r.total for r in rows) / n
        pct_exact   = 100 * sum(1 for r in rows if r.exact > 0) / n
        pct_cm      = 100 * sum(1 for r in rows if r.can_make > 0) / n
        pct_almost  = 100 * sum(1 for r in rows if r.almost > 0) / n
        zero        = sum(1 for r in rows if r.total == 0)
        out(
            f"  {size:<6} {n:<8} {avg_total:<10.1f} "
            f"{green(f'{pct_exact:.0f}%'):<20} "
            f"{cyan(f'{pct_cm:.0f}%'):<20} "
            f"{yellow(f'{pct_almost:.0f}%'):<20} "
            f"{(red(str(zero)) if zero else dim('0')):<10}"
        )
    out()

    # ── Zero result queries ────────────────────────────────────────────────────
    zero_rows = [r for r in summary if r.total == 0 and not r.error]
    if zero_rows:
        out(bold(red(f"  ✗ ZERO-RESULT QUERIES ({len(zero_rows)}):")))
        for r in zero_rows:
            out(f"    {' + '.join(r.ingredients)}")
        out()

    # ── Unmatched tokens ──────────────────────────────────────────────────────
    all_unmatched: dict[str, int] = {}
    for r in summary:
        for tok in r.unmatched:
            all_unmatched[tok] = all_unmatched.get(tok, 0) + 1
    if all_unmatched:
        out(bold(yellow("  △ UNMATCHED TOKENS (add these to the ingredient dictionary):")))
        for tok, cnt in sorted(all_unmatched.items(), key=lambda x: -x[1]):
            out(f"    {red(tok):<30} {dim(f'appeared in {cnt} queries')}")
        out()

    # ── Top performing single-ingredient searches ─────────────────────────────
    single = [r for r in summary if r.size == 1 and r.total > 0]
    if single:
        out(bold("  Top single-ingredient results (most to least matches):"))
        single_sorted = sorted(single, key=lambda r: -r.total)
        for r in single_sorted:
            tier_fn = TIER_COLOUR.get(r.top_tier, dim)
            bar = score_bar(r.top_score, width=12)
            out(
                f"    {r.ingredients[0]:<20} "
                f"{bold(str(r.total)):>4} results  "
                f"top: {bold(r.top_name):<28} "
                f"{tier_fn(TIER_LABEL.get(r.top_tier,'?').strip()):<10} "
                f"{tier_fn(bar)} {r.top_score:.3f}"
            )
        out()

    # ── Errors ────────────────────────────────────────────────────────────────
    errors = [r for r in summary if r.error]
    if errors:
        out(bold(red(f"  ✗ ERRORS ({len(errors)}):")))
        for r in errors:
            out(f"    {' + '.join(r.ingredients):<40} {red(r.error)}")
        out()

    total_ok   = sum(1 for r in summary if not r.error and r.total > 0)
    total_zero = len(zero_rows)
    total_err  = len(errors)
    total_all  = len(summary)

    out(bold("  Overall:"))
    out(f"    {green(str(total_ok))} / {total_all} queries returned results")
    if total_zero:
        out(f"    {red(str(total_zero))} zero-result queries")
    if total_err:
        out(f"    {red(str(total_err))} errors")
    out()
    out(bold(cyan("  ✓ Probe complete.")))
    out()
    out(f"  Results saved to: {bold(str(RESULTS_FILE))}")
    out()

    _outfile.close()


if __name__ == "__main__":
    main()
