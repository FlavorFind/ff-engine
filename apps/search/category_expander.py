"""
E56 — Category word expansion.

Expands category words (e.g. 'greens', 'meat') to the ingredient IDs
that belong to that category, before the GIN shortlist query.

Blueprint section 5 (The Dictionary):
  "greens, meat — Category words. The engine expands them to member
   ingredients (sukuma wiki, spinach, cabbage; beef, goat, chicken)."

Architecture section 6.1, step 3:
  "Expand: Category inputs such as 'greens' expand to member ingredients;
   staples are added to the pool unless excluded."

Pipeline position: called in resolve_ingredients() BEFORE resolve_many(),
so category-expanded IDs bypass the resolver and go straight to the pool.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from apps.curation.normaliser import normalise

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hard-coded alias map: common words → expected category slugs
#
# Category slugs come from IngredientCategory.slug (auto-derived from name_en
# in seed_all via slugify). This map covers the most common natural-language
# category words users type.
# ---------------------------------------------------------------------------

_CATEGORY_ALIASES: dict[str, list[str]] = {
    # Vegetables / greens
    "greens": ["vegetables", "vegetables-and-greens", "vegetables-greens"],
    "vegetables": ["vegetables", "vegetables-and-greens", "vegetables-greens"],
    "veggies": ["vegetables", "vegetables-and-greens", "vegetables-greens"],
    "mboga": ["vegetables", "vegetables-and-greens"],  # Swahili for vegetables
    "majani": ["vegetables", "vegetables-and-greens"],  # Swahili: leafy greens
    # Meat
    "meat": ["meat", "meat-offal-and-poultry", "meat-offal-poultry"],
    "nyama": ["meat", "meat-offal-and-poultry", "meat-offal-poultry"],  # Swahili: meat
    # Poultry
    "poultry": ["poultry", "meat-offal-and-poultry", "meat-offal-poultry"],
    "chicken": None,  # handled by _GENERIC_INGREDIENT_SLUGS below
    # Fish / seafood
    "fish": ["fish-and-seafood", "fish-seafood", "fish"],
    "seafood": ["fish-and-seafood", "fish-seafood"],
    "samaki": ["fish-and-seafood", "fish-seafood"],  # Swahili: fish
    # Grains / starches
    "grains": ["grains", "grains-flours-and-starches", "grains-flours-starches"],
    "starches": ["grains", "grains-flours-and-starches", "grains-flours-starches"],
    "flour": ["grains", "grains-flours-and-starches", "grains-flours-starches"],
    # Legumes / pulses
    "legumes": ["legumes", "legumes-and-pulses"],
    "pulses": ["legumes", "legumes-and-pulses"],
    "beans": None,  # 'beans' is an ingredient — skip
    # Dairy
    "dairy": ["dairy", "dairy-and-eggs", "dairy-eggs"],
    "maziwa": ["dairy", "dairy-and-eggs"],  # Swahili: milk/dairy
    # Spices / seasonings
    "spices": ["spices", "spices-herbs-and-seasonings", "spices-and-seasonings"],
    "seasonings": ["spices", "spices-herbs-and-seasonings"],
    "herbs": ["spices", "spices-herbs-and-seasonings"],
    # Oils / fats
    "oils": ["fats-oils", "fats-and-oils", "oils-fats-and-sauces"],
    "oil": None,  # 'oil' is an ingredient — skip
    # Fruits
    "fruits": ["fruit", "fruits"],
    "matunda": ["fruit", "fruits"],  # Swahili: fruits
    # Nuts and seeds
    "nuts": ["nuts-and-seeds", "nuts-seeds"],
    "seeds": ["nuts-and-seeds", "nuts-seeds"],
}


# ---------------------------------------------------------------------------
# Generic ingredient expansion map
#
# When a user types a generic term like "chicken" that has no dishes using
# the bare ingredient slug, expand it to all the specific cuts/variants that
# are actually used in dish data.  This is keyed on the normalised token.
# ---------------------------------------------------------------------------

_GENERIC_INGREDIENT_SLUGS: dict[str, list[str]] = {
    "chicken": [
        "chicken-pieces",
        "chicken-breast",
        "chicken-thighs",
        "chicken-drumsticks",
        "whole-chicken",
        "chicken-wings",
        "free-range-chicken",
        "chicken",  # include bare slug too in case any dishes do use it
    ],
    "kuku": [  # Swahili: chicken
        "chicken-pieces",
        "chicken-breast",
        "chicken-thighs",
        "chicken-drumsticks",
        "whole-chicken",
        "chicken-wings",
        "free-range-chicken",
        "chicken",
    ],
    "beef": [
        "beef",
        "minced-beef",
        "beef-mince",
        "ground-beef",
        "beef-steak",
        "beef-strips",
        "beef-chunks",
        "beef-cubes",
        "beef-ribs",
        "beef-short-ribs",
        "beef-sirloin",
        "beef-tenderloin",
        "beef-fillet",
        "beef-brisket",
        "beef-shank",
        "beef-shin",
        "beef-chuck",
        "beef-neck",
        "beef-shoulder",
        "beef-rump",
        "beef-flank",
        "beef-liver",
        "beef-kidney",
        "beef-heart",
        "beef-tripe",
        "beef-offal",
        "oxtail",
        "corned-beef",
    ],
    "nyama-ya-ngombe": ["beef", "minced-beef", "beef-chunks", "beef-cubes"],  # Swahili: beef
    "fish": [
        "tilapia",
        "tilapia-fillets",
        "nile-perch",
        "sardines",
        "mackerel",
        "omena",
        "dagaa",
        "dried-fish",
        "smoked-fish",
        "fish",
    ],
    "samaki": [  # Swahili: fish
        "tilapia",
        "tilapia-fillets",
        "nile-perch",
        "omena",
        "dagaa",
        "dried-fish",
        "smoked-fish",
    ],
    "goat": [
        "goat",
        "goat-meat",
        "goat-chunks",
        "goat-ribs",
        "goat-chops",
        "goat-loin",
        "goat-shoulder",
        "goat-neck",
        "goat-legs",
        "whole-goat",
        "minced-goat",
        "dried-goat-meat",
    ],
    "mbuzi": [  # Swahili: goat
        "goat",
        "goat-meat",
        "goat-chunks",
        "goat-ribs",
        "whole-goat",
        "minced-goat",
    ],
    "lamb": [
        "lamb",
        "lamb-shoulder",
        "lamb-chops",
        "lamb-cutlets",
        "lamb-rack",
        "lamb-leg",
        "lamb-neck",
        "lamb-ribs",
        "lamb-shank",
        "lamb-mince",
        "minced-lamb",
        "mutton",
        "mutton-chunks",
        "mutton-ribs",
    ],
    "kondoo": ["lamb", "lamb-chops", "mutton"],  # Swahili: sheep/lamb
    "pork": [
        "pork",
        "pork-belly",
        "pork-ribs",
        "pork-chops",
        "pork-shoulder",
        "pork-loin",
        "pork-neck",
        "pork-mince",
        "minced-pork",
        "pork-trotters",
        "pork-knuckle",
        "bacon",
        "ham",
        "pork-sausages",
    ],
    "nguruwe": ["pork", "pork-belly", "pork-ribs"],  # Swahili: pig/pork
    # Game meat
    "game": [
        "warthog-meat", "impala-meat", "eland-meat", "buffalo-meat",
        "zebra-meat", "hartebeest-meat", "springbok-meat", "bush-pig-meat",
        "venison", "rabbit-meat",
    ],
    "bushmeat": [
        "warthog-meat", "impala-meat", "eland-meat", "buffalo-meat",
        "zebra-meat", "hartebeest-meat", "springbok-meat", "bush-pig-meat",
        "porcupine-meat",
    ],
    "warthog": ["warthog-meat"],
    "ngiri": ["warthog-meat"],  # Swahili
    "impala": ["impala-meat"],
    "swala": ["impala-meat"],   # Swahili
    "eland": ["eland-meat"],
    "pofu": ["eland-meat"],     # Swahili
    "buffalo": ["buffalo-meat"],
    "nyati": ["buffalo-meat"],  # Swahili
    "venison": ["venison", "impala-meat", "hartebeest-meat", "eland-meat"],
    # Offal — generic
    "offal": [
        "mixed-offal", "offal-mix", "beef-offal",
        "beef-tripe", "beef-intestines", "beef-liver", "beef-kidney", "beef-heart",
        "goat-tripe", "goat-intestines", "goat-liver", "goat-kidney", "goat-heart",
        "chicken-gizzards", "chicken-liver", "chicken-feet",
        "pork-liver", "pork-kidney", "pork-heart", "pork-intestines",
    ],
    "matumbo": [
        "mixed-offal", "offal-mix", "beef-tripe", "beef-intestines",
        "goat-tripe", "goat-intestines", "pork-intestines",
    ],  # Swahili: intestines/tripe
    "tripe": ["beef-tripe", "goat-tripe", "lamb-tripe", "mixed-offal"],
    # Poultry — generic
    "turkey": ["turkey-breast", "turkey-legs", "turkey-mince", "turkey"],
    "bata-mzinga": ["turkey-breast", "turkey-legs", "turkey"],  # Swahili: turkey
    "duck": ["duck", "duck-breast", "duck-legs", "duck-meat"],
    "bata": ["duck", "duck-breast", "duck-legs", "duck-meat"],  # Swahili: duck
    "guinea-fowl": ["guinea-fowl", "guinea-fowl-pieces"],
    "kanga": ["guinea-fowl", "guinea-fowl-pieces"],  # Swahili: guinea fowl
    # Processed / deli — generic
    "sausage": [
        "beef-sausages", "pork-sausages", "smoked-sausage", "chorizo",
        "merguez", "frankfurter", "hotdog", "blood-sausage", "salami",
    ],
    "soseji": [
        "beef-sausages", "pork-sausages", "smoked-sausage", "frankfurter",
    ],  # Swahili: sausage
    "shawarma": [
        "chicken-shawarma-meat", "beef-shawarma-meat", "lamb-shawarma-meat",
    ],
    "meatballs": ["beef-meatballs", "chicken-meatballs", "lamb-meatballs"],
    "kofta": ["beef-meatballs", "lamb-meatballs", "chicken-meatballs"],
    # Vegetables — generic
    "tomatoes": ["tomato", "cherry-tomatoes", "roma-tomatoes", "plum-tomatoes",
                 "sun-dried-tomatoes", "canned-tomatoes", "green-tomatoes"],
    "nyanya": ["tomato", "cherry-tomatoes", "roma-tomatoes", "canned-tomatoes"],
    "peppers": ["green-pepper", "red-bell-pepper", "yellow-bell-pepper", "capsicum",
                "red-chili", "green-chili", "scotch-bonnet", "habanero",
                "bird-eye-chili", "long-green-chili", "dried-chili"],
    "pilipili": ["green-pepper", "red-bell-pepper", "yellow-bell-pepper",
                 "red-chili", "green-chili", "bird-eye-chili", "dried-chili"],
    "chili": ["red-chili", "green-chili", "bird-eye-chili", "long-green-chili",
              "dried-chili", "chili-flakes", "scotch-bonnet", "habanero"],
    "onions": ["onion", "red-onion", "spring-onions", "shallots", "green-onion",
               "dried-onion"],
    "vitunguu": ["onion", "red-onion", "spring-onions", "shallots"],
    "garlic": ["garlic", "garlic-cloves", "garlic-powder"],
    "saumu": ["garlic", "garlic-cloves"],
    "mushrooms": ["mushrooms", "oyster-mushrooms", "termite-mushrooms",
                  "wild-chanterelles", "dried-mushrooms"],
    "uyoga": ["mushrooms", "oyster-mushrooms", "termite-mushrooms", "dried-mushrooms"],
    "greens": ["spinach", "kale", "collard-greens", "amaranth-leaves",
               "baby-spinach", "swiss-chard", "mustard-greens", "beet-greens",
               "mchicha-leaves", "cowpea-leaves", "pumpkin-leaves",
               "sweet-potato-leaves", "cassava-leaves", "moringa-leaves",
               "nderema", "mchunga", "osuga", "bondwe", "african-nightshade"],
    "mboga": ["spinach", "kale", "collard-greens", "amaranth-leaves",
              "cowpea-leaves", "pumpkin-leaves", "cassava-leaves",
              "nderema", "mchunga", "osuga", "bondwe"],
    "mchicha": ["spinach", "amaranth-leaves", "baby-spinach", "mchicha-leaves",
                "bondwe"],
    "sukuma": ["kale", "collard-greens"],
    "sukuma-wiki": ["kale", "collard-greens"],
    "squash": ["butternut-squash", "acorn-squash", "spaghetti-squash",
               "pattypan-squash", "butternut-cubes"],
    "boga": ["pumpkin", "butternut-squash", "acorn-squash", "butternut-cubes"],
    "yam": ["yam", "white-yam", "water-yam", "wild-yams", "purple-yam",
            "elephant-foot-yam"],
    "viazi": ["potato", "sweet-potato", "sweet-potato-purple", "white-sweet-potato",
              "orange-fleshed-sweet-potato"],
    "viazi-vikuu": ["yam", "white-yam", "water-yam", "cocoyam"],
    "frozen": ["frozen-peas", "frozen-corn", "frozen-spinach"],
    "canned": ["canned-tomatoes", "canned-beef", "luncheon-meat"],
}


@lru_cache(maxsize=128)
def _get_generic_ingredient_ids(norm_token: str) -> list[str]:
    """
    Return ingredient UUIDs for a generic token (e.g. 'chicken') by looking
    up each slug in _GENERIC_INGREDIENT_SLUGS.  Cached per token.
    """
    slugs = _GENERIC_INGREDIENT_SLUGS.get(norm_token)
    if not slugs:
        return []

    from apps.ingredients.models import Ingredient

    ids = list(
        Ingredient.objects.filter(slug__in=slugs).values_list("id", flat=True)
    )
    return [str(iid) for iid in ids]


def invalidate_generic_cache() -> None:
    """Clear the generic ingredient cache.  Call in tests or after bulk imports."""
    _get_generic_ingredient_ids.cache_clear()


def expand_category_terms(
    raw_tokens: list[str],
) -> tuple[list[str], list[str]]:
    """
    Check each raw token against the category word list.

    Parameters
    ----------
    raw_tokens:
        List of raw ingredient strings from the caller.

    Returns
    -------
    (expanded_ids, remaining_tokens)
        expanded_ids    — UUID strings of all ingredients in matched categories
        remaining_tokens — tokens that did NOT match any category (pass to resolver)
    """
    expanded_ids: list[str] = []
    remaining: list[str] = []

    for token in raw_tokens:
        norm = normalise(token)

        # ── Generic ingredient expansion (e.g. 'chicken' → all cuts) ──────────
        generic_ids = _get_generic_ingredient_ids(norm)
        if generic_ids:
            expanded_ids.extend(generic_ids)
            logger.debug(
                "category_expander: %r → %d IDs via generic expansion", token, len(generic_ids)
            )
            continue

        candidate_slugs = _CATEGORY_ALIASES.get(norm)

        if candidate_slugs is None:
            # Token is in the alias map with value=None (it's an ingredient, not category)
            remaining.append(token)
            continue

        if norm not in _CATEGORY_ALIASES:
            # Token not in the alias map at all
            remaining.append(token)
            continue

        ids = _resolve_category_to_ids(candidate_slugs)
        if ids:
            expanded_ids.extend(ids)
            logger.debug("category_expander: %r → %d ingredient IDs via category", token, len(ids))
        else:
            # No matching category found in DB — treat as normal ingredient token
            remaining.append(token)

    # Deduplicate expanded IDs while preserving order
    seen: set[str] = set()
    unique_ids: list[str] = []
    for iid in expanded_ids:
        if iid not in seen:
            seen.add(iid)
            unique_ids.append(iid)

    return unique_ids, remaining


def _resolve_category_to_ids(candidate_slugs: list[str]) -> list[str]:
    """
    Try each slug in candidate_slugs until one matches a category in the DB.
    Returns the ingredient IDs for all ingredients in that category
    (including children via parent FK).
    """
    for slug in candidate_slugs:
        ids = _get_category_ingredient_ids(slug)
        if ids:
            return ids
    return []


def get_category_ingredient_ids(category_slug: str) -> list[str]:
    """
    Public interface: return all ingredient UUID strings for the given category,
    including any child sub-categories.
    """
    return _get_category_ingredient_ids(category_slug)


@lru_cache(maxsize=64)
def _get_category_ingredient_ids(category_slug: str) -> list[str]:
    """
    Return ingredient UUIDs for a category slug (and its children).
    Result is cached per slug for the process lifetime.

    Cache is invalidated in tests via invalidate_category_cache().
    """
    from apps.ingredients.models import Ingredient, IngredientCategory

    try:
        cat = IngredientCategory.objects.filter(slug=category_slug).first()
        if cat is None:
            return []

        # Collect this category and all children (one level deep for v1)
        cat_ids = [cat.pk]
        child_ids = list(IngredientCategory.objects.filter(parent=cat).values_list("id", flat=True))
        cat_ids.extend(child_ids)

        ids = list(Ingredient.objects.filter(category_id__in=cat_ids).values_list("id", flat=True))
        return [str(iid) for iid in ids]
    except Exception as exc:
        logger.warning("category_expander: failed to fetch category %r: %s", category_slug, exc)
        return []


def invalidate_category_cache() -> None:
    """Clear the LRU cache. Call after bulk-importing new categories or in tests."""
    _get_category_ingredient_ids.cache_clear()
