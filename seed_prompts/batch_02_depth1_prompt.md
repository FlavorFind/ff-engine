# FF-Engine Seed Prompt — Batch 02
# Depth 1: One hero dish per ingredient (ingredients 26–50)
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

26. cabbage
27. spinach
28. kale
29. collard-greens
30. potato
31. carrot
32. green-pepper
33. sweet-potato
34. pumpkin
35. eggplant
36. okra
37. mushrooms
38. amaranth-leaves
39. cowpea-leaves
40. eggs
41. milk
42. yogurt
43. avocado
44. banana
45. green-bananas
46. coconut
47. mango
48. passion-fruit
49. tamarind-pulp
50. papaya

---

## OUTPUT FORMAT

Output a single JSON array of 25 dish objects. Each object must follow this exact schema:

```
{
  "slug": "kenyan-cabbage-stew",
  "name_en": "Kenyan Cabbage Stew",
  "name_sw": "Mchuzi wa Kabichi",
  "description": "A simple and nutritious Kenyan cabbage stew cooked with tomatoes and onions, commonly served with ugali.",
  "meal_type": "lunch",
  "course": "main",
  "spice_level": "mild",
  "difficulty": "easy",
  "prep_min": 10,
  "cook_min": 25,
  "servings": 4,
  "regions": ["kenya"],
  "ingredients": [
    {"slug": "cabbage", "role": "primary", "quantity": "1", "unit": "medium head"},
    {"slug": "tomato", "role": "required", "quantity": "3", "unit": "medium"},
    {"slug": "onion", "role": "required", "quantity": "1", "unit": "medium"},
    {"slug": "garlic", "role": "optional", "quantity": "2", "unit": "cloves"},
    {"slug": "cooking-oil", "role": "staple", "quantity": "2", "unit": "tbsp"},
    {"slug": "salt", "role": "staple", "quantity": "1", "unit": "tsp"}
  ],
  "steps": [
    {"order": 1, "instruction": "Heat oil in a pan over medium heat. Add onions and fry until translucent, about 3 minutes."},
    {"order": 2, "instruction": "Add garlic and tomatoes. Cook stirring until tomatoes break down into a sauce, about 5 minutes."},
    {"order": 3, "instruction": "Add shredded cabbage and stir to combine with the sauce. Season with salt."},
    {"order": 4, "instruction": "Cover and cook on low heat for 10 minutes until cabbage is tender but not mushy. Serve hot."}
  ],
  "nutrition_per_serving": {
    "calories": 95,
    "protein_g": 3,
    "carbs_g": 12,
    "fat_g": 4,
    "fiber_g": 4
  },
  "dietary_tags": ["vegan", "gluten-free", "dairy-free", "egg-free", "nut-free", "halal-friendly"],
  "serving_suggestion": "Serve with ugali or chapati."
}
```

---

Now generate the 25 dishes. Output only the JSON array, nothing else.
