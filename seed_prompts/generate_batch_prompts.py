#!/usr/bin/env python3
"""
Generate DeepSeek batch prompts for the 98-ingredient seed pipeline.

Creates 10 batch prompt files (batch_07_*.md through batch_16_*.md),
each targeting ~10 ingredients sorted by least-covered first.
Each prompt asks DeepSeek for ~50 Kenyan dishes.

Usage:
    python seed_prompts/generate_batch_prompts.py
"""

import csv
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).parent.parent
SEEDS = ROOT / "data" / "seeds"
OUT = ROOT / "seed_prompts"

# ── Load ingredients ──────────────────────────────────────────────────────────
ingredients = {}
with open(SEEDS / "ingredients.csv") as f:
    for row in csv.DictReader(f):
        ingredients[row["slug"]] = {
            "name": row["name_en"],
            "category": row.get("category", ""),
            "staple": row.get("is_staple", "").lower() in ("true", "1", "yes"),
        }

# ── Load dish counts ─────────────────────────────────────────────────────────
dish_counts: dict[str, int] = {}
with open(SEEDS / "dish_ingredients.csv") as f:
    for row in csv.DictReader(f):
        slug = row.get("ingredient_slug", "").strip()
        if slug:
            dish_counts[slug] = dish_counts.get(slug, 0) + 1

# ── Build allowed-slugs block (grouped by category) ─────────────────────────
cats: dict[str, list[tuple[str, str, bool]]] = {}
for slug, info in ingredients.items():
    cats.setdefault(info["category"], []).append((slug, info["name"], info["staple"]))

slugs_block_lines = []
staples_block_lines = []
for cat in sorted(cats):
    items = sorted(cats[cat], key=lambda x: x[0])
    slugs_block_lines.append(f"### {cat} ({len(items)})")
    for slug, name, staple in items:
        if staple:
            staples_block_lines.append(f"- `{slug}` ({name})")
        else:
            slugs_block_lines.append(f"- `{slug}` ({name})")
    slugs_block_lines.append("")

slugs_block = "\n".join(slugs_block_lines)
staples_block = "\n".join(staples_block_lines)

# ── Define batches (prioritise least-covered, culinary-compatible) ───────────
#  Sorted by dish count ascending.  Each batch tries to mix categories
#  so DeepSeek can generate realistic Kenyan dishes.

batches = [
    # Batch 07 — 1-dish fruits + fats
    [
        "coconut-oil",
        "ghee",
        "groundnut-oil",
        "avocado",
        "mango",
        "papaya",
        "passion-fruit",
        "green-bananas",
        "green-plantains",
        "ripe-plantain",
    ],
    # Batch 08 — 1-dish legumes + grains + fish + meat
    [
        "black-eyed-peas",
        "chickpeas",
        "kidney-beans",
        "red-lentils",
        "yellow-lentils",
        "sorghum-flour",
        "ugali-meal",
        "minced-beef",
        "tamarind-pulp",
        "dried-fish",
    ],
    # Batch 09 — 1-dish poultry + spices + veg
    [
        "chicken-breast",
        "chicken-thighs",
        "chicken-drumsticks",
        "whole-chicken",
        "garam-masala",
        "lemongrass",
        "mchuzi-mix",
        "black-pepper",
        "amaranth-leaves",
        "arrowroot",
    ],
    # Batch 10 — 1-dish vegetables + dairy
    [
        "cassava",
        "cowpea-leaves",
        "cucumber",
        "eggplant",
        "mushrooms",
        "okra",
        "pumpkin",
        "spring-onions",
        "butter",
        "fresh-milk",
    ],
    # Batch 11 — 2-dish proteins + dairy + fruit
    [
        "goat-meat",
        "beef-liver",
        "dagaa",
        "nile-perch",
        "smoked-fish",
        "tilapia-fillets",
        "pigeon-peas",
        "lentils-or-minced-beef",
        "sour-milk",
        "banana",
    ],
    # Batch 12 — 2-dish spices + veg + fish + grains
    [
        "cinnamon",
        "ground-cumin",
        "mint",
        "paprika",
        "turmeric",
        "kale",
        "sweet-potato",
        "omena",
        "maize",
        "millet-flour",
    ],
    # Batch 13 — 3-4 dish ingredients
    [
        "beef-ribs",
        "beef-tripe",
        "cardamom",
        "green-beans",
        "yogurt",
        "maize-flour",
        "green-grams",
        "groundnuts",
        "cabbage",
        "collard-greens",
    ],
    # Batch 14 — 4-9 dish ingredients
    [
        "spinach",
        "tilapia",
        "green-pepper",
        "pilau-masala",
        "carrot",
        "milk",
        "chili",
        "potato",
        "red-onion",
        "eggs",
    ],
    # Batch 15 — 9-16 dish ingredients
    [
        "wheat-flour",
        "lemon",
        "lime",
        "rice",
        "beans",
        "chicken-pieces",
        "beef",
        "sugar",
        "coriander",
        "coconut",
    ],
    # Batch 16 — most-used (already well covered, fewer new dishes needed)
    ["curry-powder", "ginger", "garlic", "water", "tomato", "onion", "cooking-oil", "salt"],
]

# ── Prompt template ──────────────────────────────────────────────────────────

PROMPT_TEMPLATE = dedent("""\
    # FF-Engine Seed Prompt — Batch {batch_num:02d}
    # Target: {dish_count} Kenyan dishes from {ing_count} hero ingredients
    # Paste this entire prompt into DeepSeek chat

    ---

    You are a Kenyan cuisine expert and structured data generator. Your job is to generate recipe data in strict JSON format for a food search engine focused on **Kenyan cuisine only**.

    ## RULES — read carefully before generating

    1. Every dish must be a **real, commonly cooked Kenyan dish** — not invented, not from other countries.
    2. Each dish must have one ingredient with role `primary` — the hero of the dish (in the name or concept).
    3. Use **only ingredient slugs from the ALLOWED SLUGS list** below. Do not invent slugs. Do not use slugs not in the list.
    4. Every dish must have:
       - At least **3 cooking steps** (clear, practical instructions a home cook can follow)
       - **Nutrition per serving** (estimate is fine but must be realistic)
       - Swahili name (`name_sw`) — use real Swahili, leave empty string if truly unknown
       - `regions` must always be `["kenya"]`
       - `dietary_tags` — pick only from: `halal-friendly`, `vegetarian`, `vegan`, `gluten-free`, `dairy-free`, `egg-free`, `nut-free`
    5. Ingredient roles:
       - `primary` — the hero of the dish (exactly 1 per dish)
       - `required` — must have, dish doesn't work without it
       - `optional` — adds flavour but dish works without it
       - `staple` — only use these slugs with role `staple`: {staples_inline}
    6. Output **only valid JSON** — no markdown, no explanation, no comments. Just the JSON array.
    7. Generate **exactly {dish_count} dishes**.
    8. Each hero ingredient below must be the `primary` in **at least {min_per_hero} dishes**.
    9. Maximise variety — different cooking methods, different meal types, different courses.
    10. Use multiple hero ingredients per dish where it makes culinary sense (e.g., "Beef and Potato Stew").

    ---

    ## ALLOWED SLUGS (only use these — {total_count} ingredients)

    {slugs_block}

    ## STAPLES (role = "staple" only)

    {staples_block}

    ---

    ## HERO INGREDIENTS FOR THIS BATCH ({ing_count} ingredients)
    Generate at least {min_per_hero} dishes where each of these is the `primary` ingredient:

    {hero_list}

    ---

    ## OUTPUT FORMAT

    Output a single JSON array of {dish_count} dish objects. Each object must follow this exact schema:

    ```json
    {{
      "slug": "kenyan-ugali",
      "name_en": "Ugali",
      "name_sw": "Ugali",
      "description": "A stiff maize flour porridge that is the staple food of Kenya, served with vegetables, meat or fish.",
      "meal_type": "lunch",
      "course": "main",
      "spice_level": "mild",
      "difficulty": "easy",
      "prep_min": 5,
      "cook_min": 20,
      "servings": 4,
      "regions": ["kenya"],
      "ingredients": [
        {{"slug": "maize-flour", "role": "primary", "quantity": "2", "unit": "cups"}},
        {{"slug": "water", "role": "staple", "quantity": "4", "unit": "cups"}},
        {{"slug": "salt", "role": "staple", "quantity": "0.5", "unit": "tsp"}}
      ],
      "steps": [
        {{"order": 1, "instruction": "Bring 4 cups of water to a boil in a heavy pot. Add a pinch of salt."}},
        {{"order": 2, "instruction": "Gradually add maize flour while stirring continuously with a wooden spoon to prevent lumps."}},
        {{"order": 3, "instruction": "Reduce heat to low. Continue stirring and folding the ugali for 8–10 minutes until it pulls away from the sides of the pot and forms a firm, smooth ball."}},
        {{"order": 4, "instruction": "Shape into a mound using a wet spoon. Serve hot on a plate alongside sukuma wiki, beans, or stew."}}
      ],
      "nutrition_per_serving": {{
        "calories": 280,
        "protein_g": 6,
        "carbs_g": 58,
        "fat_g": 2,
        "fiber_g": 3
      }},
      "dietary_tags": ["vegan", "gluten-free", "dairy-free", "egg-free", "nut-free"],
      "serving_suggestion": "Serve with sukuma wiki, beans stew, or any meat dish."
    }}
    ```

    Valid enum values:
    - `meal_type`: breakfast, lunch, dinner, snack
    - `course`: main, side, dessert, snack, drink
    - `spice_level`: mild, medium, hot
    - `difficulty`: easy, medium, hard

    ---

    Now generate the {dish_count} dishes. Output only the JSON array, nothing else.
""")

# ── Generate prompt files ────────────────────────────────────────────────────

staples_inline = ", ".join(
    f"`{slug}`"
    for slug, _, staple in sorted(
        [(s, i["name"], i["staple"]) for s, i in ingredients.items() if i["staple"]],
        key=lambda x: x[0],
    )
)

batch_num = 7  # continue after existing batches 1-6
for batch in batches:
    ing_count = len(batch)
    # More dishes for under-covered ingredients
    total_coverage = sum(dish_counts.get(s, 0) for s in batch)
    if total_coverage <= 12:  # all 1-dish ingredients
        dish_count = 50
    elif total_coverage <= 25:  # mostly 2-dish
        dish_count = 45
    elif total_coverage <= 50:  # 3-4 dish
        dish_count = 40
    else:  # well-covered
        dish_count = 30

    min_per_hero = max(3, dish_count // (ing_count + 5))

    hero_lines = []
    for i, slug in enumerate(batch, 1):
        info = ingredients[slug]
        count = dish_counts.get(slug, 0)
        hero_lines.append(f"{i}. `{slug}` ({info['name']}) — currently in {count} dish(es)")
    hero_list = "\n".join(hero_lines)

    prompt = PROMPT_TEMPLATE.format(
        batch_num=batch_num,
        dish_count=dish_count,
        ing_count=ing_count,
        min_per_hero=min_per_hero,
        total_count=len(ingredients),
        slugs_block=slugs_block,
        staples_block=staples_block,
        staples_inline=staples_inline,
        hero_list=hero_list,
    )

    fname = OUT / f"batch_{batch_num:02d}_prompt.md"
    fname.write_text(prompt)
    print(f"  {fname.name} — {ing_count} ingredients, {dish_count} dishes, min {min_per_hero}/hero")
    batch_num += 1

print(f"\nGenerated {len(batches)} batch prompts in {OUT}/")
print(
    f"Total target dishes: ~{sum(50 if sum(dish_counts.get(s,0) for s in b) <= 12 else 45 if sum(dish_counts.get(s,0) for s in b) <= 25 else 40 if sum(dish_counts.get(s,0) for s in b) <= 50 else 30 for b in batches)}"
)
print(
    f"Combined with existing 150 dishes → ~{150 + sum(50 if sum(dish_counts.get(s,0) for s in b) <= 12 else 45 if sum(dish_counts.get(s,0) for s in b) <= 25 else 40 if sum(dish_counts.get(s,0) for s in b) <= 50 else 30 for b in batches)} total"
)
