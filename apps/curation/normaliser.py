"""
E15 — The Cleaner (normaliser).

Normalises raw text into a canonical form used by the importer, validator,
resolver and search pipeline.

Pipeline (matches Architecture section 6.1, step 1):
  1. Unicode → ASCII (basic transliteration)
  2. Lowercase
  3. Strip leading/trailing whitespace
  4. Collapse internal whitespace
  5. Remove punctuation (keep hyphens between words, apostrophes stripped)
  6. Strip leading quantities ("2 tomatoes" → "tomatoes", "1 kg salt" → "salt")
  7. Strip trailing plural 's' for common patterns (tomatoes → tomato)
  8. Detect probable language (en / sw / sheng / other) — heuristic only

Usage::

    from apps.curation.normaliser import normalise, detect_language

    normalise("2 Tomatoes!")         # → "tomato"
    normalise("sukuma wiki")         # → "sukuma wiki"
    detect_language("nyanya")        # → "sw"
    detect_language("tomato")        # → "en"
"""

from __future__ import annotations

import re
import unicodedata

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = ["normalise", "detect_language", "NormaliseResult"]

from dataclasses import dataclass


@dataclass
class NormaliseResult:
    """Return value from normalise() — carries the cleaned text and metadata."""

    raw: str
    normalised: str
    language: str  # "en" | "sw" | "sheng" | "other"
    quantity_stripped: str  # the leading quantity removed, if any (e.g. "2")
    unit_stripped: str  # unit removed alongside the quantity (e.g. "kg")


def normalise(text: str) -> str:
    """
    Return the normalised form of *text*.

    Quick version — just the string.  Use normalise_full() for metadata.
    """
    return normalise_full(text).normalised


def normalise_full(text: str) -> NormaliseResult:
    """
    Full normalisation with metadata (quantity stripped, language guess).
    """
    raw = text
    t = _unicode_to_ascii(text)
    t = t.lower()
    t = t.strip()
    t = _collapse_whitespace(t)

    qty, unit, t = _strip_leading_quantity(t)

    t = _remove_punctuation(t)
    t = _collapse_whitespace(t).strip()
    t = _strip_plural(t)

    lang = detect_language(t)
    return NormaliseResult(
        raw=raw,
        normalised=t,
        language=lang,
        quantity_stripped=qty,
        unit_stripped=unit,
    )


def detect_language(text: str) -> str:
    """
    Heuristic language detection: "en" | "sw" | "sheng" | "other".

    Not a full NLP classifier — fast pattern matching against common
    Swahili ingredient words and known Sheng terms.  Falls back to "en".
    """
    t = text.lower().strip()
    if _is_sheng(t):
        return "sheng"
    if _is_swahili(t):
        return "sw"
    if _looks_english(t):
        return "en"
    return "other"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Leading quantity patterns: "2", "2.5", "1/2", "½" followed by optional unit
_QTY_RE = re.compile(
    r"^"
    r"(?P<qty>\d+(?:[.,]\d+)?(?:/\d+)?|\u00bd|\u2153|\u2154|\u00bc|\u00be)"  # number or fraction char
    r"\s*"
    r"(?P<unit>kg|g|ml|l|litre|liter|cup|cups|tbsp|tsp|bunch|handful|pinch|piece|pieces|slice|slices|clove|cloves|can|cans|tin|tins|stalk|stalks|head|heads|leaf|leaves)?"
    r"\s+",
    re.IGNORECASE,
)

# Punctuation to remove (keep hyphens between word chars)
_PUNCT_RE = re.compile(r"[^\w\s-]")
# Hyphens only between non-word chars → remove dangling hyphens
_DANGLE_HYPHEN_RE = re.compile(r"(?<!\w)-|-(?!\w)")

# Simple plural rule: trailing 's' after a vowel+consonant pattern
# e.g. tomatoes→tomato, onions→onion, carrots→carrot
# Does NOT strip: grass, bass, class, etc.
_PLURAL_RE = re.compile(
    r"(?:"
    r"(oes)$|"  # tomatoes → tomato
    r"(ies)$|"  # berries → berry  (replace with y)
    r"(?<=[aeiou][^aeiou])(s)$|"  # onions, carrots → onion, carrot
    r"(?<=[^aeiou])(es)$"  # mangoes handled by oes above; dishes→dish
    r")"
)


def _unicode_to_ascii(text: str) -> str:
    """Transliterate common accented characters to ASCII equivalents."""
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def _collapse_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _strip_leading_quantity(text: str) -> tuple[str, str, str]:
    """
    Remove a leading quantity + optional unit from text.

    Returns (qty_string, unit_string, remaining_text).
    """
    m = _QTY_RE.match(text)
    if m:
        qty = m.group("qty") or ""
        unit = m.group("unit") or ""
        remaining = text[m.end() :]
        return qty, unit, remaining
    return "", "", text


def _remove_punctuation(text: str) -> str:
    t = _PUNCT_RE.sub(" ", text)
    t = _DANGLE_HYPHEN_RE.sub(" ", t)
    return t


def _strip_plural(text: str) -> str:
    """
    Very conservative plural stripping — only well-known English patterns.
    Applied per token so "sukuma wiki" is untouched.
    """
    tokens = text.split()
    result = []
    for token in tokens:
        result.append(_deplural_token(token))
    return " ".join(result)


def _deplural_token(word: str) -> str:
    """
    Conservative English plural → singular.
    Only strips endings where the stem is clearly correct.
    Does NOT process short words (≤3 chars) or words ending in 'ss'.
    """
    if len(word) <= 3 or word.endswith("ss"):
        return word

    # "oes" ending: tomatoes → tomato, potatoes → potato
    if word.endswith("oes") and len(word) > 4:
        return word[:-2]  # remove 'es'

    # "ves" ending: leaves → leaf
    # Only apply for well-known "f→ves" or direct "ve→ves" patterns
    _VES_TO_LEAF = {
        "leaves": "leaf",
        "knives": "knife",
        "lives": "life",
        "halves": "half",
        "wolves": "wolf",
        "shelves": "shelf",
        # "ve→ves" words (not f→ves): cloves→clove, stoves→stove, grooves→groove
        "cloves": "clove",
        "stoves": "stove",
        "grooves": "groove",
        "gloves": "glove",
        "groves": "grove",
    }
    if word in _VES_TO_LEAF:
        return _VES_TO_LEAF[word]

    # "ies" ending: berries → berry
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"

    # "shes" → "sh": dishes → dish, brushes → brush
    if word.endswith("shes"):
        return word[:-2]

    # "ches" → "ch": bunches → bunch
    if word.endswith("ches"):
        return word[:-2]

    # "xes" → "x": boxes → box
    if word.endswith("xes"):
        return word[:-2]

    # "zes" → "z"
    if word.endswith("zes"):
        return word[:-2]

    # "nes" ending: sardines → sardine, bones → bone, stones → stone
    if word.endswith("nes") and len(word) > 4:
        return word[:-1]

    # "kes" ending: flakes → flake, cakes → cake, cloves handled by ves above
    if word.endswith("kes") and len(word) > 4:
        return word[:-1]

    # "ces" ending: pieces → piece, slices → slice
    if word.endswith("ces") and len(word) > 4:
        return word[:-1]

    # "ges" ending: changes → change, pages → page
    if word.endswith("ges") and len(word) > 4:
        return word[:-1]

    # "les" ending: noodles → noodle, angles → angle
    if word.endswith("les") and len(word) > 4:
        return word[:-1]

    # "nas" ending: bananas → banana
    if word.endswith("nas") and len(word) > 4:
        return word[:-1]

    # "ps" ending after vowel: chops → chop, chips → chip, ribs handled below
    if word.endswith("ps") and len(word) > 3 and word[-3] in "aeiou":
        return word[:-1]

    # "bs" ending: ribs → rib
    if word.endswith("bs") and len(word) > 3 and word[-3] in "aeiou":
        return word[:-1]

    # "gs" ending: eggs → egg, legs → leg
    if word.endswith("gs") and len(word) > 3:
        return word[:-1]

    # "ts" ending: fillets → fillet
    if word.endswith("ts") and len(word) > 3 and word[-3] in "aeiou":
        return word[:-1]

    # Simple trailing 's' after vowel: onions→onion, carrots→carrot
    # Only when: ends in consonant+s, char before consonant is vowel, no double-s
    if (
        word.endswith("s")
        and not word.endswith("ss")
        and len(word) > 3
        and word[-2] not in "aeiousxyz"
        and len(word) >= 4
        and word[-3] in "aeiou"
    ):
        return word[:-1]

    return word


# ---------------------------------------------------------------------------
# Language detection word lists
# ---------------------------------------------------------------------------

# Common Swahili ingredient / food words
_SWAHILI_WORDS = frozenset(
    """
    nyanya pilipili vitunguu sukuma managu terere kisamvu mchuzi uji ugali
    mahindi maharage kunde njahi ndizi matoke maziwa nyama samaki kuku
    mafuta chumvi sukari unga chapati mandazi maharagwe viazi mchicha
    mwembe papai embe parachichi tunda mboga pilau biryani wali chai
    ndengu mchicha mchele mbari matambwe muhogo mihogo
    """.split()
)

# Known Sheng food terms (extend as data grows)
_SHENG_WORDS = frozenset(
    """
    nyam chom mtura kuku wa kienyeji nyums
    """.split()
)

# Very common English words that should always map to "en"
_ENGLISH_WORDS = frozenset(
    """
    tomato potato onion garlic ginger carrot spinach cabbage beef chicken
    fish salt sugar oil flour rice beans lentil pepper coriander lime lemon
    avocado mango banana pineapple egg butter milk cream cheese bread
    """.split()
)


def _is_swahili(text: str) -> bool:
    tokens = set(text.split())
    return bool(tokens & _SWAHILI_WORDS)


def _is_sheng(text: str) -> bool:
    tokens = set(text.split())
    return bool(tokens & _SHENG_WORDS)


def _looks_english(text: str) -> bool:
    tokens = set(text.split())
    if tokens & _ENGLISH_WORDS:
        return True
    # Fallback: mostly ASCII letters — assume English
    ascii_ratio = sum(1 for c in text if c.isascii() and c.isalpha()) / max(len(text), 1)
    return ascii_ratio > 0.85
