# FF-Engine Seed Prompt — Batch 06
# Depth 3–6: Full Kenyan recipes with 3–8 ingredients
# Paste this entire prompt into DeepSeek chat

---

You are a Kenyan cuisine expert and structured data generator. Your job is to generate recipe data in strict JSON format for a food search engine focused on **Kenyan cuisine only**.

## RULES — read carefully before generating

1. Every dish must be a **real, commonly cooked Kenyan dish** — not invented, not from other countries.
2. Each dish must use all the listed **key ingredients** as `primary` or `required` roles.
3. Use **only ingredient slugs from the ALLOWED SLUGS list** below. Do not invent slugs.
4. Every dish must have:
   - At least **4 cooking steps** (detailed, practical, home-cook friendly)
   - **Nutrition per serving**
   - Swahili name (`name_sw`)
   - `regions` must always be `["kenya"]`
   - `dietary_tags` — pick only from: `halal-friendly`, `vegetarian`, `vegan`, `gluten-free`, `dairy-free`, `egg-free`, `nut-free`
5. Ingredient roles:
   - `primary` — the main hero (1 per dish)
   - `required` — must have, dish doesn't work without it
   - `optional` — adds flavour, dish works without it
   - `staple` — only use: `salt`, `cooking-oil`, `water`, `black-pepper`
6. Output **only valid JSON** — no markdown, no explanation, no comments. Just the JSON array.
7. Generate **exactly 25 dishes** — one for each recipe in the TARGET RECIPES list below.

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

## TARGET RECIPES FOR THIS BATCH
Each entry shows the dish name and the KEY ingredients it must include (as primary or required). You may add more from the allowed list as optional:

**3-ingredient dishes (depth 3)**
1.  Kenyan Sukuma Wiki — collard-greens + onion + tomato
2.  Kenyan Githeri — maize + beans + onion
3.  Kenyan Chapati — wheat-flour + milk + cooking-oil (note: cooking-oil is staple but here it's required in dough — mark it required)
4.  Kenyan Mukimo — potato + green-peas + spinach  (use green-beans instead of green-peas since it's in allowed list)
5.  Kenyan Ugali na Sukuma — maize-flour + collard-greens + onion
6.  Kenyan Fish Curry — tilapia + tomato + curry-powder
7.  Kenyan Chicken Stew — chicken-pieces + tomato + onion
8.  Kenyan Matumbo — beef-tripe + onion + tomato
9.  Kenyan Nyama Choma — beef-ribs + lemon + garlic
10. Kenyan Kachumbari — tomato + red-onion + lemon

**4-ingredient dishes (depth 4)**
11. Kenyan Chicken Curry — chicken-pieces + onion + tomato + curry-powder
12. Kenyan Beef Pilau — rice + beef + pilau-masala + onion
13. Kenyan Githeri Stew — maize + beans + tomato + onion
14. Kenyan Samaki wa Nazi — tilapia + coconut + tomato + onion
15. Kenyan Lentil Soup — lentils-or-minced-beef + onion + tomato + garlic
16. Kenyan Bean Soup — beans + onion + tomato + garlic

**5-ingredient dishes (depth 5)**
17. Kenyan Chicken Pilau — rice + chicken-pieces + pilau-masala + onion + garlic
18. Kenyan Vegetable Stew — cabbage + carrot + potato + onion + tomato
19. Kenyan Omena Stew — omena + onion + tomato + green-pepper + garlic
20. Kenyan Coconut Bean Stew — beans + coconut + onion + tomato + garlic

**6-ingredient dishes (depth 6)**
21. Kenyan Full Biryani — rice + chicken-pieces + onion + tomato + garlic + ginger
22. Kenyan Beef Stew Classic — beef + potato + onion + tomato + garlic + ginger
23. Kenyan Coconut Fish Curry — tilapia-fillets + coconut + onion + tomato + garlic + ginger
24. Kenyan Groundnut Chicken — chicken-pieces + groundnuts + onion + tomato + garlic + ginger
25. Kenyan Mixed Vegetable Curry — potato + carrot + green-beans + onion + tomato + curry-powder

---

## OUTPUT FORMAT

Output a single JSON array of 25 dish objects. Each object must follow this exact schema:

```
{
  "slug": "kenyan-sukuma-wiki",
  "name_en": "Kenyan Sukuma Wiki",
  "name_sw": "Sukuma Wiki",
  "description": "Sautéed collard greens cooked with tomatoes and onions. Kenya's most popular everyday vegetable side dish, the name means 'push the week' in Swahili.",
  "meal_type": "lunch",
  "course": "side",
  "spice_level": "mild",
  "difficulty": "easy",
  "prep_min": 10,
  "cook_min": 15,
  "servings": 4,
  "regions": ["kenya"],
  "ingredients": [
    {"slug": "collard-greens", "role": "primary", "quantity": "500", "unit": "g"},
    {"slug": "onion", "role": "required", "quantity": "1", "unit": "large"},
    {"slug": "tomato", "role": "required", "quantity": "2", "unit": "medium"},
    {"slug": "garlic", "role": "optional", "quantity": "2", "unit": "cloves"},
    {"slug": "cooking-oil", "role": "staple", "quantity": "2", "unit": "tbsp"},
    {"slug": "salt", "role": "staple", "quantity": "1", "unit": "tsp"}
  ],
  "steps": [
    {"order": 1, "instruction": "Wash the collard greens thoroughly. Remove tough stems and slice leaves into thin strips."},
    {"order": 2, "instruction": "Heat oil in a wide pan over medium heat. Add onions and fry until soft and translucent, about 4 minutes."},
    {"order": 3, "instruction": "Add garlic if using, then add chopped tomatoes. Cook stirring until tomatoes break down and form a sauce, about 5 minutes."},
    {"order": 4, "instruction": "Add the sliced collard greens and toss to coat with the sauce. Season with salt. Cook for 5–7 minutes until greens are wilted but still bright green. Do not overcook."},
    {"order": 5, "instruction": "Taste and adjust seasoning. Serve immediately alongside ugali, rice or chapati."}
  ],
  "nutrition_per_serving": {
    "calories": 85,
    "protein_g": 4,
    "carbs_g": 9,
    "fat_g": 4,
    "fiber_g": 5
  },
  "dietary_tags": ["vegan", "gluten-free", "dairy-free", "egg-free", "nut-free", "halal-friendly"],
  "serving_suggestion": "Always served alongside ugali. The classic Kenyan combination."
}
```

---

Now generate the 25 dishes. Output only the JSON array, nothing else.
