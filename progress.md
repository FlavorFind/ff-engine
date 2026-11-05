# FF-Engine Seed Data Progress

## Goal
~500 Kenyan dishes from 98 ingredients. Each ingredient in 3+ dishes.

## Ingredient Cleanup
- [x] Archived 783 unused ingredients → `data/seeds/archive_20261104_203850/`
- [x] Trimmed `ingredients.csv` to 98 ingredients
- [x] Updated `validate_batch.py` to load slugs dynamically

## Batch Tracking

| Batch | File | Hero Ingredients | Dishes | Status | Notes |
|-------|------|-----------------|--------|--------|-------|
| 01-06 | existing | 25 per batch | 150 | ✅ seeded | Already in database |
| 07 | `batch_07_prompt.md` | 10 (1-dish each) | 50 | ✅ validated | 6 dup slugs vs existing |
| 08 | `batch_08_prompt.md` | 10 (1-dish each) | 50 | ✅ validated | 5 dup slugs vs existing |
| 09 | `batch_09_prompt.md` | 10 (1-dish each) | 50 | ✅ validated | 2 dup slugs vs existing |
| 10 | `batch_10_prompt.md` | 10 (1-dish each) | 50 | ✅ validated | 4 dup slugs vs existing |
| 11 | `batch_11_prompt.md` | 10 (2-dish each) | 45 | ✅ validated | 0 failures |
| 12 | `batch_12_prompt.md` | 10 (2-dish each) | 46 | ✅ validated | 0 failures |
| 13 | `batch_13_prompt.md` | 10 (3-4 dish) | 42 | ✅ validated | 0 failures |
| 14 | `batch_14_prompt.md` | 10 (4-9 dish) | 30 | ✅ validated | 0 failures |
| 15 | `batch_15_prompt.md` | 10 heroes: wheat-flour, lemon, lime, rice, beans, chicken-pieces, beef, sugar, coriander, coconut | 30 | ✅ validated | 0 failures |
| 16 | `batch_16_prompt.md` | 8 heroes: curry-powder, ginger, garlic, water, tomato, onion, cooking-oil, salt | 28 | ✅ validated | 0 failures — 28 dishes (pure-staple primaries skipped) |

## Totals
- Batches 01-06: 150 dishes ✅ seeded
- Batch 07: 50 dishes ✅
- Batch 08: 50 dishes ✅
- Batch 09: 50 dishes ✅
- Batch 10: 50 dishes ✅
- Batch 11: 45 dishes ✅
- Batch 12: 46 dishes ✅
- Batch 13: 42 dishes ✅
- Batch 14: 30 dishes ✅
- Batch 15: 30 dishes ✅
- Batch 16: 28 dishes ✅
- **Current total: 571 dishes — ALL BATCHES COMPLETE ✅**
- **Grand total target: ~573 dishes — ACHIEVED**

## Next Step: Seed to Database
All batch outputs validated. Run:
```
python3 seed_prompts/build_seed_csvs.py --wipe
```

## Workflow
1. Copy `seed_prompts/batch_XX_prompt.md` into DeepSeek
2. Paste JSON output → save + validate:
   ```
   python3 seed_prompts/save_and_validate.py <N> < output.json
   ```
3. After all batches done → merge + seed DB:
   ```
   python3 seed_prompts/build_seed_csvs.py --wipe
   ```

## Batch 16 Details
- Output: `seed_prompts/outputs/batch_16_output.json`
- 28 dishes passed validation (0 failures)
- Hero ingredients: curry-powder, ginger, garlic, tomato, onion (water/salt/cooking-oil primaries skipped — not real dishes)

## Batch 15 Details
- Output: `seed_prompts/outputs/batch_15_output.json`
- All 30 dishes passed validation (0 failures)
- Hero ingredients: wheat-flour, lemon, lime, rice, beans, chicken-pieces, beef, sugar, coriander, coconut
- Notable: kenyan-bean-soup has `course: starter` (valid enum), kenyan-coriander-chutney has `course: condiment`

## Batch 14 Details
- Output: `seed_prompts/outputs/batch_14_output.json`
- All 30 dishes passed validation (0 failures)
- Hero ingredients: spinach, tilapia, green-pepper, pilau-masala, carrot, milk, chili, potato, red-onion, eggs

## Batch 13 Details
- Output: `seed_prompts/outputs/batch_13_output.json`
- 42 dishes passed validation (0 failures)

## Batch 12 Details
- Output: `seed_prompts/outputs/batch_12_output.json`
- 46 dishes passed validation (0 failures)

## Batch 11 Details
- Output: `seed_prompts/outputs/batch_11_output.json`
- 45 dishes passed validation (0 failures)

## Batch 10 Details
- Output: `seed_prompts/outputs/batch_10_output.json`
- All 50 dishes passed validation
- 4 duplicate slugs vs existing

## Batch 09 Details
- Output: `seed_prompts/outputs/batch_09_output.json`
- All 50 dishes passed validation
- 2 duplicate slugs vs existing

## Batch 08 Details
- Output: `seed_prompts/outputs/batch_08_output.json`
- All 50 dishes passed validation
- 5 duplicate slugs (will overwrite older versions on merge):
  - kenyan-chickpea-stew, kenyan-minced-beef-stew, kenyan-red-lentil-stew
  - kenyan-sorghum-ugali, kenyan-tamarind-drink
- Fixes applied during save:
  - 4 soups had `"course": "starter"` → fixed to `"main"` (not a valid enum)
  - ugali dish slug renamed from `kenyan-ugali` to `kenyan-ugali-meal-plain` (avoid dup)

## Batch 07 Details
- Output: `seed_prompts/outputs/batch_07_output.json`
- All 50 dishes passed validation
- 6 duplicate slugs (will overwrite older versions on merge):
  - kenyan-avocado-salad, kenyan-mango-salsa, kenyan-papaya-salad
  - kenyan-passion-fruit-juice, kenyan-green-banana-stew, kenyan-ghee-halwa

## Batch 15 Hero Ingredients
wheat-flour (in 9 dishes), lemon (10), lime (10), rice (11), beans (11),
chicken-pieces (11), beef (12), sugar (13), coriander (14), coconut (16)

## Batch 16 Hero Ingredients
curry-powder (18), ginger (20), garlic (73), water (95), tomato (95),
onion (107), cooking-oil (118), salt (141)
— Note: batch 16 heroes are the most-used ingredients across all dishes,
so dishes must be truly unique and not repeat what's already seeded.
