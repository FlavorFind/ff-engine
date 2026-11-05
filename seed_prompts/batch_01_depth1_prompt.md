# FF-Engine Seed Prompt — Batch 01
# Depth 1: One hero dish per ingredient (first 25 ingredients)
# Paste this entire prompt into DeepSeek chat

---

You are a Kenyan cuisine expert and structured data generator. Your job is to generate recipe data in strict JSON format for a food search engine focused on **Kenyan cuisine only**.

## RULES — read carefully before generating

1. Every dish must be a **real, commonly cooked Kenyan dish** — not invented, not from other countries.
2. Each dish must have the **hero ingredient** as its `primary` role ingredient — it must be central to the dish (in the name or concept).
3. Use **only ingredient slugs from the ALLOWED SLUGS list** below. Do not invent slugs. Do not use slugs not in the list.
4. Every dish must have:
   - At least **3 cooking steps** (clear, practical instructions a home cook can follow)
   - **Nutrition per serving** (estimate is fine but must be realistic)
   - Swahili name (`name_sw`) — use real Swahili, leave empty string if truly unknown
   - `regions` must always be `["kenya"]`
   - `dietary_tags` — pick only from: `halal-friendly`, `vegetarian`, `vegan`, `gluten-free`, `dairy-free`, `egg-free`, `nut-free`
5. Ingredient roles:
   - `primary` — the hero of the dish (1 per dish)
   - `required` — must have, dish doesn't work without it
   - `optional` — adds flavour but dish works without it
   - `staple` — only use: `salt`, `cooking-oil`, `water`, `black-pepper`
6. Output **only valid JSON** — no markdown, no explanation, no comments. Just the JSON array.
7. Generate **exactly 25 dishes** — one for each ingredient in the TARGET INGREDIENTS list below.

---

## ALLOWED SLUGS (only use these)

### Grains & Starches
maize-flour, rice, wheat-flour, sorghum-flour, millet-flour, cassava, arrowroot, ugali-meal, maize

### Proteins — Meat
beef, goat-meat, chicken-pieces, whole-chicken, beef-liver, beef-tripe, minced-beef, beef-ribs, chicken-breast, chicken-thighs, chicken-drumsticks

### Proteins — Fish
tilapia, omena, dagaa, tilapia-fillets, nile-perch, dried-fish, smoked-fish

### Proteins — Legumes
beans, green-grams, lentils-or-minced-beef, pigeon-peas, groundnuts, chickpeas, kidney-beans, black-eyed-peas, red-lentils, yellow-lentils

### Vegetables
onion, tomato, cabbage, spinach, kale, collard-greens, potato, potatoes, carrot, green-pepper, red-onion, sweet-potato, pumpkin, eggplant, green-beans, cucumber, amaranth-leaves, cowpea-leaves, okra, mushrooms, spring-onions

### Fruits (used in cooking)
banana, green-bananas, mango, avocado, lemon, lime, coconut, green-plantains, ripe-plantain, passion-fruit, papaya, tamarind-pulp

### Dairy & Eggs
eggs, milk, fresh-milk, yogurt, butter, ghee, sour-milk

### Fats & Oils
coconut-oil, sunflower-oil, groundnut-oil, palm-oil

### Spices & Seasonings
garlic, ginger, coriander, turmeric, ground-cumin, cardamom, cinnamon, pilau-masala, curry-powder, chili, paprika, pepper, bay-leaves, cloves, thyme, mint, mchuzi-mix, garam-masala, lemongrass, sugar

### Staples (role = "staple" only)
salt, cooking-oil, water, black-pepper

---

## TARGET INGREDIENTS FOR THIS BATCH
Generate exactly one dish where each of these is the `primary` ingredient:

1. maize-flour
2. rice
3. wheat-flour
4. cassava
5. arrowroot
6. maize
7. beef
8. goat-meat
9. chicken-pieces
10. beef-liver
11. beef-tripe
12. minced-beef
13. beef-ribs
14. tilapia
15. omena
16. dagaa
17. nile-perch
18. beans
19. green-grams
20. pigeon-peas
21. groundnuts
22. kidney-beans
23. red-lentils
24. onion
25. tomato

---

## OUTPUT FORMAT

Output a single JSON array of 25 dish objects. Each object must follow this exact schema:

```
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

---

Now generate the 25 dishes. Output only the JSON array, nothing else.
