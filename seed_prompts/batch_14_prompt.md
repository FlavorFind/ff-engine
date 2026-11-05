# FF-Engine Seed Prompt — Batch 14
# Target: 30 Kenyan dishes from 10 hero ingredients
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
   - `staple` — only use these slugs with role `staple`: `black-pepper`, `cooking-oil`, `salt`, `water`
6. Output **only valid JSON** — no markdown, no explanation, no comments. Just the JSON array.
7. Generate **exactly 30 dishes**.
8. Each hero ingredient below must be the `primary` in **at least 3 dishes**.
9. Maximise variety — different cooking methods, different meal types, different courses.
10. Use multiple hero ingredients per dish where it makes culinary sense (e.g., "Beef and Potato Stew").

---

## ALLOWED SLUGS (only use these — 98 ingredients)

### Dairy & Eggs (6)
- `butter` (butter)
- `eggs` (eggs)
- `fresh-milk` (fresh milk)
- `milk` (milk)
- `sour-milk` (Sour milk)
- `yogurt` (Yogurt)

### Fats & Oils (4)
- `coconut-oil` (Coconut oil)
- `ghee` (Ghee)
- `groundnut-oil` (Groundnut oil)

### Fish & Seafood (7)
- `dagaa` (Dagaa)
- `dried-fish` (dried fish)
- `nile-perch` (Nile perch)
- `omena` (Omena)
- `smoked-fish` (Smoked fish)
- `tilapia` (tilapia)
- `tilapia-fillets` (tilapia fillets)

### Fruit (12)
- `avocado` (avocado)
- `banana` (banana)
- `coconut` (Coconut)
- `green-bananas` (green bananas)
- `green-plantains` (green plantains)
- `lemon` (lemon)
- `lime` (lime)
- `mango` (mango)
- `papaya` (Papaya)
- `passion-fruit` (passion fruit)
- `ripe-plantain` (ripe plantain)
- `tamarind-pulp` (Tamarind pulp)

### Grains (7)
- `maize` (maize)
- `maize-flour` (maize flour)
- `millet-flour` (millet flour)
- `rice` (rice)
- `sorghum-flour` (Sorghum flour)
- `ugali-meal` (Ugali meal (sifted maize meal))
- `wheat-flour` (wheat flour)

### Legumes (10)
- `beans` (beans)
- `black-eyed-peas` (black-eyed peas)
- `chickpeas` (chickpeas)
- `green-grams` (green grams)
- `groundnuts` (groundnuts)
- `kidney-beans` (kidney beans)
- `lentils-or-minced-beef` (lentils or minced beef)
- `pigeon-peas` (Pigeon peas)
- `red-lentils` (red lentils)
- `yellow-lentils` (Yellow lentils)

### Liquids (1)

### Meat (6)
- `beef` (beef)
- `beef-liver` (Beef liver)
- `beef-ribs` (beef ribs)
- `beef-tripe` (beef tripe)
- `goat-meat` (goat meat)
- `minced-beef` (minced beef)

### Other (1)
- `sugar` (sugar)

### Poultry (5)
- `chicken-breast` (Chicken breast)
- `chicken-drumsticks` (Chicken drumsticks)
- `chicken-pieces` (chicken pieces)
- `chicken-thighs` (Chicken thighs)
- `whole-chicken` (Whole chicken)

### Spices & Seasonings (17)
- `cardamom` (cardamom)
- `chili` (chili)
- `cinnamon` (cinnamon)
- `coriander` (coriander)
- `curry-powder` (curry powder)
- `garam-masala` (Garam masala)
- `garlic` (garlic)
- `ginger` (ginger)
- `ground-cumin` (Ground cumin)
- `lemongrass` (Lemongrass)
- `mchuzi-mix` (Mchuzi mix)
- `mint` (Mint)
- `paprika` (Paprika)
- `pilau-masala` (pilau masala)
- `turmeric` (turmeric)

### Vegetables (22)
- `amaranth-leaves` (amaranth leaves)
- `arrowroot` (Arrowroot)
- `cabbage` (cabbage)
- `carrot` (carrot)
- `cassava` (cassava)
- `collard-greens` (collard greens)
- `cowpea-leaves` (Cowpea leaves)
- `cucumber` (Cucumber)
- `eggplant` (eggplant)
- `green-beans` (green beans)
- `green-pepper` (green pepper)
- `kale` (Kale)
- `mushrooms` (Mushrooms)
- `okra` (Okra)
- `onion` (onion)
- `potato` (potato)
- `pumpkin` (pumpkin)
- `red-onion` (red onion)
- `spinach` (spinach)
- `spring-onions` (Spring onions)
- `sweet-potato` (sweet potato)
- `tomato` (tomato)


## STAPLES (role = "staple" only)

- `cooking-oil` (cooking oil)
- `water` (water)
- `black-pepper` (black pepper)
- `salt` (salt)

---

## HERO INGREDIENTS FOR THIS BATCH (10 ingredients)
Generate at least 3 dishes where each of these is the `primary` ingredient:

1. `spinach` (spinach) — currently in 4 dish(es)
2. `tilapia` (tilapia) — currently in 5 dish(es)
3. `green-pepper` (green pepper) — currently in 5 dish(es)
4. `pilau-masala` (pilau masala) — currently in 6 dish(es)
5. `carrot` (carrot) — currently in 6 dish(es)
6. `milk` (milk) — currently in 8 dish(es)
7. `chili` (chili) — currently in 8 dish(es)
8. `potato` (potato) — currently in 8 dish(es)
9. `red-onion` (red onion) — currently in 8 dish(es)
10. `eggs` (eggs) — currently in 9 dish(es)

---

## OUTPUT FORMAT

Output a single JSON array of 30 dish objects. Each object must follow this exact schema:

```json
{
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
    {"slug": "maize-flour", "role": "primary", "quantity": "2", "unit": "cups"},
    {"slug": "water", "role": "staple", "quantity": "4", "unit": "cups"},
    {"slug": "salt", "role": "staple", "quantity": "0.5", "unit": "tsp"}
  ],
  "steps": [
    {"order": 1, "instruction": "Bring 4 cups of water to a boil in a heavy pot. Add a pinch of salt."},
    {"order": 2, "instruction": "Gradually add maize flour while stirring continuously with a wooden spoon to prevent lumps."},
    {"order": 3, "instruction": "Reduce heat to low. Continue stirring and folding the ugali for 8–10 minutes until it pulls away from the sides of the pot and forms a firm, smooth ball."},
    {"order": 4, "instruction": "Shape into a mound using a wet spoon. Serve hot on a plate alongside sukuma wiki, beans, or stew."}
  ],
  "nutrition_per_serving": {
    "calories": 280,
    "protein_g": 6,
    "carbs_g": 58,
    "fat_g": 2,
    "fiber_g": 3
  },
  "dietary_tags": ["vegan", "gluten-free", "dairy-free", "egg-free", "nut-free"],
  "serving_suggestion": "Serve with sukuma wiki, beans stew, or any meat dish."
}
```

Valid enum values:
- `meal_type`: breakfast, lunch, dinner, snack
- `course`: main, side, dessert, snack, drink
- `spice_level`: mild, medium, hot
- `difficulty`: easy, medium, hard

---

Now generate the 30 dishes. Output only the JSON array, nothing else.
