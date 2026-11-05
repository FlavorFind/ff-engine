# FF-Engine Seed Prompt — Batch 03
# Depth 1: One hero dish per ingredient (ingredients 51–75)
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

51. garlic
52. ginger
53. coriander
54. turmeric
55. pilau-masala
56. cardamom
57. cinnamon
58. ghee
59. butter
60. sour-milk
61. green-plantains
62. ripe-plantain
63. lemon
64. lime
65. whole-chicken
66. chicken-breast
67. chicken-thighs
68. chicken-drumsticks
69. beef-liver
70. beef-tripe  (use the Kenyan name matumbo)
71. beef-ribs
72. smoked-fish
73. dried-fish
74. black-eyed-peas
75. yellow-lentils

---

## OUTPUT FORMAT

Output a single JSON array of 25 dish objects. Each object must follow this exact schema:

```
{
  "slug": "kenyan-pilau",
  "name_en": "Kenyan Pilau",
  "name_sw": "Pilau",
  "description": "A fragrant Kenyan spiced rice dish cooked with pilau masala, beef and caramelised onions. A festive staple at Kenyan celebrations and weddings.",
  "meal_type": "lunch",
  "course": "main",
  "spice_level": "medium",
  "difficulty": "medium",
  "prep_min": 20,
  "cook_min": 60,
  "servings": 6,
  "regions": ["kenya"],
  "ingredients": [
    {"slug": "pilau-masala", "role": "primary", "quantity": "2", "unit": "tbsp"},
    {"slug": "rice", "role": "required", "quantity": "3", "unit": "cups"},
    {"slug": "beef", "role": "required", "quantity": "500", "unit": "g"},
    {"slug": "onion", "role": "required", "quantity": "2", "unit": "large"},
    {"slug": "garlic", "role": "required", "quantity": "4", "unit": "cloves"},
    {"slug": "ginger", "role": "required", "quantity": "1", "unit": "inch piece"},
    {"slug": "potato", "role": "optional", "quantity": "2", "unit": "medium"},
    {"slug": "cooking-oil", "role": "staple", "quantity": "3", "unit": "tbsp"},
    {"slug": "salt", "role": "staple", "quantity": "2", "unit": "tsp"},
    {"slug": "water", "role": "staple", "quantity": "5", "unit": "cups"}
  ],
  "steps": [
    {"order": 1, "instruction": "Heat oil in a heavy pot. Add onions and fry on medium heat until deep golden brown, about 15 minutes. This caramelisation is key to pilau's flavour."},
    {"order": 2, "instruction": "Add garlic, ginger and pilau masala. Stir and fry for 2 minutes until fragrant."},
    {"order": 3, "instruction": "Add beef pieces and brown on all sides. Add potatoes if using. Pour in 2 cups water, cover and cook until beef is tender, about 30 minutes."},
    {"order": 4, "instruction": "Add washed rice and remaining water. Season with salt. Stir once, cover tightly and cook on low heat for 20 minutes until rice absorbs all water."},
    {"order": 5, "instruction": "Remove from heat and let steam for 5 minutes with lid on. Fluff gently and serve."}
  ],
  "nutrition_per_serving": {
    "calories": 520,
    "protein_g": 28,
    "carbs_g": 65,
    "fat_g": 14,
    "fiber_g": 3
  },
  "dietary_tags": ["halal-friendly", "dairy-free", "egg-free", "nut-free"],
  "serving_suggestion": "Serve with kachumbari (tomato and onion salad) and a cold drink."
}
```

---

Now generate the 25 dishes. Output only the JSON array, nothing else.
