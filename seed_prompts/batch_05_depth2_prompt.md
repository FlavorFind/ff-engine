# FF-Engine Seed Prompt — Batch 05
# Depth 2: Classic Kenyan 2-ingredient combination dishes
# Paste this entire prompt into DeepSeek chat

---

You are a Kenyan cuisine expert and structured data generator. Your job is to generate recipe data in strict JSON format for a food search engine focused on **Kenyan cuisine only**.

## RULES — read carefully before generating

1. Every dish must be a **real, commonly cooked Kenyan dish** — not invented, not from other countries.
2. Each dish must use **both listed ingredients** as either `primary` or `required` roles — these are the two key ingredients that define the dish.
3. Use **only ingredient slugs from the ALLOWED SLUGS list** below. Do not invent slugs.
4. Every dish must have:
   - At least **4 cooking steps**
   - **Nutrition per serving**
   - Swahili name (`name_sw`)
   - `regions` must always be `["kenya"]`
   - `dietary_tags` — pick only from: `halal-friendly`, `vegetarian`, `vegan`, `gluten-free`, `dairy-free`, `egg-free`, `nut-free`
5. Ingredient roles:
   - `primary` — the main hero (1 per dish, pick the most important of the two listed)
   - `required` — must have
   - `optional` — adds flavour but dish works without it
   - `staple` — only use: `salt`, `cooking-oil`, `water`, `black-pepper`
6. Output **only valid JSON** — no markdown, no explanation, no comments. Just the JSON array.
7. Generate **exactly 25 dishes** — one for each pair in the TARGET PAIRS list below.

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

## TARGET PAIRS FOR THIS BATCH
Generate exactly one dish for each pair. Both ingredients in the pair must appear in the dish as `primary` or `required`:

1.  beef + onion
2.  beef + potato
3.  beef + tomato
4.  goat-meat + onion
5.  chicken-pieces + tomato
6.  chicken-pieces + onion
7.  tilapia + onion
8.  tilapia + tomato
9.  omena + tomato
10. beans + maize-flour
11. beans + onion
12. beans + tomato
13. green-grams + onion
14. green-grams + coconut
15. maize-flour + beans
16. rice + beans
17. rice + coconut
18. collard-greens + onion
19. cabbage + carrot
20. sweet-potato + beans
21. eggs + tomato
22. eggs + onion
23. groundnuts + spinach
24. pigeon-peas + coconut
25. lentils-or-minced-beef + onion

---

## OUTPUT FORMAT

Output a single JSON array of 25 dish objects. Each object must follow this exact schema:

```
{
  "slug": "kenyan-beef-and-potato-stew",
  "name_en": "Kenyan Beef and Potato Stew",
  "name_sw": "Mchuzi wa Nyama na Viazi",
  "description": "A rich Kenyan beef stew with soft potatoes, slow-cooked in a tomato and onion sauce. A family favourite served with ugali or rice.",
  "meal_type": "lunch",
  "course": "main",
  "spice_level": "medium",
  "difficulty": "easy",
  "prep_min": 15,
  "cook_min": 60,
  "servings": 5,
  "regions": ["kenya"],
  "ingredients": [
    {"slug": "beef", "role": "primary", "quantity": "600", "unit": "g cubed"},
    {"slug": "potato", "role": "required", "quantity": "4", "unit": "medium"},
    {"slug": "tomato", "role": "required", "quantity": "3", "unit": "medium"},
    {"slug": "onion", "role": "required", "quantity": "2", "unit": "medium"},
    {"slug": "garlic", "role": "optional", "quantity": "3", "unit": "cloves"},
    {"slug": "curry-powder", "role": "optional", "quantity": "1", "unit": "tsp"},
    {"slug": "cooking-oil", "role": "staple", "quantity": "3", "unit": "tbsp"},
    {"slug": "salt", "role": "staple", "quantity": "1.5", "unit": "tsp"},
    {"slug": "water", "role": "staple", "quantity": "2", "unit": "cups"}
  ],
  "steps": [
    {"order": 1, "instruction": "Heat oil in a heavy pot. Brown the beef cubes in batches over high heat. Remove and set aside."},
    {"order": 2, "instruction": "In the same pot, fry onions until golden. Add garlic and curry powder, stir for 1 minute."},
    {"order": 3, "instruction": "Add tomatoes and cook until they form a thick sauce. Return the beef to the pot."},
    {"order": 4, "instruction": "Add water, cover and simmer on low heat for 30 minutes. Add potatoes and cook for a further 20 minutes until both beef and potatoes are tender."},
    {"order": 5, "instruction": "Adjust seasoning and serve hot with ugali or rice."}
  ],
  "nutrition_per_serving": {
    "calories": 380,
    "protein_g": 32,
    "carbs_g": 28,
    "fat_g": 16,
    "fiber_g": 3
  },
  "dietary_tags": ["halal-friendly", "gluten-free", "dairy-free", "egg-free", "nut-free"],
  "serving_suggestion": "Serve with ugali, rice or chapati and a side of kachumbari."
}
```

---

Now generate the 25 dishes. Output only the JSON array, nothing else.
