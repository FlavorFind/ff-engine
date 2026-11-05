# FF-Engine Seed Prompt — Batch 04
# Depth 1: One hero dish per ingredient (ingredients 76–100)
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

76. chickpeas
77. green-beans
78. cucumber
79. red-onion
80. spring-onions
81. sorghum-flour
82. millet-flour
83. ugali-meal
84. fresh-milk
85. eggs  (a second egg dish, different from batch 02 — make it a street food)
86. coconut-oil
87. groundnut-oil
88. curry-powder
89. mchuzi-mix
90. garam-masala
91. chili
92. mint
93. lemongrass
94. sugar
95. green-pepper
96. tilapia-fillets
97. dagaa
98. nile-perch
99. smoked-fish
100. sour-milk

---

## OUTPUT FORMAT

Output a single JSON array of 25 dish objects. Each object must follow this exact schema:

```
{
  "slug": "kenyan-chickpea-stew",
  "name_en": "Kenyan Chickpea Stew",
  "name_sw": "Mchuzi wa Dengu za Hindi",
  "description": "A hearty Kenyan chickpea stew slow-cooked with tomatoes, onions and spices. Popular as a filling vegetarian meal served with rice or chapati.",
  "meal_type": "lunch",
  "course": "main",
  "spice_level": "medium",
  "difficulty": "easy",
  "prep_min": 10,
  "cook_min": 40,
  "servings": 4,
  "regions": ["kenya"],
  "ingredients": [
    {"slug": "chickpeas", "role": "primary", "quantity": "400", "unit": "g cooked"},
    {"slug": "tomato", "role": "required", "quantity": "3", "unit": "medium"},
    {"slug": "onion", "role": "required", "quantity": "1", "unit": "large"},
    {"slug": "garlic", "role": "required", "quantity": "3", "unit": "cloves"},
    {"slug": "ginger", "role": "optional", "quantity": "1", "unit": "tsp grated"},
    {"slug": "curry-powder", "role": "optional", "quantity": "1", "unit": "tsp"},
    {"slug": "cooking-oil", "role": "staple", "quantity": "2", "unit": "tbsp"},
    {"slug": "salt", "role": "staple", "quantity": "1", "unit": "tsp"}
  ],
  "steps": [
    {"order": 1, "instruction": "Heat oil in a pot over medium heat. Add chopped onions and fry until golden, about 5 minutes."},
    {"order": 2, "instruction": "Add garlic, ginger and curry powder. Stir and cook for 1 minute until fragrant."},
    {"order": 3, "instruction": "Add chopped tomatoes and cook until they break down into a thick sauce, about 8 minutes."},
    {"order": 4, "instruction": "Add cooked chickpeas and 1 cup water. Stir well, season with salt and simmer for 15 minutes until sauce thickens. Serve hot."}
  ],
  "nutrition_per_serving": {
    "calories": 280,
    "protein_g": 12,
    "carbs_g": 38,
    "fat_g": 8,
    "fiber_g": 9
  },
  "dietary_tags": ["vegan", "gluten-free", "dairy-free", "egg-free", "halal-friendly"],
  "serving_suggestion": "Serve with chapati or steamed rice."
}
```

---

Now generate the 25 dishes. Output only the JSON array, nothing else.
