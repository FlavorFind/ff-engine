# Data Style Guide — Flavor Find Engine

**Version:** 1.0.0  
**Applies to:** `data/seeds/*.csv`, `data/golden/*.json`

---

## Principles

1. **Slugs are permanent.** Once a slug is in the seed and deployed, it is a public API contract. Never rename or delete a slug — add an alias instead.
2. **One ingredient, one slug.** Do not create duplicates (e.g. `tomato` and `tomatoes`). Use aliases for alternate forms.
3. **Names are display strings.** `name_en` and `name_sw` are shown to users. Title-case proper nouns; lowercase common nouns.
4. **Descriptions are one sentence.** 10–20 words. No full stops at the end.
5. **All required fields must be filled.** The QA report (`qa_report`) will flag blanks.

---

## Slug Rules

- Lowercase, hyphen-separated: `chicken-pieces`, `maize-flour`
- No underscores, no spaces, no special characters
- Use the most common English name as the base
- For regional names, use English slug + Swahili alias: slug `pilau`, alias `wali wa pilau`
- For cuts/variants, add the variant after the base: `beef-sirloin`, `lamb-shank`

### Good examples

| Slug | Name |
|------|------|
| `chicken-pieces` | Chicken pieces |
| `maize-flour` | Maize flour |
| `ground-cumin` | Ground cumin |
| `beef-short-ribs` | Beef short ribs |

### Bad examples

| Slug (wrong) | Problem |
|-------------|---------|
| `Chicken_Pieces` | Uppercase + underscore |
| `chicken pieces` | Space |
| `chkn-pcs` | Abbreviation |
| `chicken-pieces-2` | Numeric suffix (use a more descriptive name) |

---

## Ingredient Categories

Use exactly these category strings (case-sensitive):

| Category | For |
|----------|-----|
| `Vegetables` | Fresh and dried vegetables |
| `Fruit` | Fresh, dried, canned fruit |
| `Meat` | Red meat, game, offal, processed meat |
| `Poultry` | Chicken, duck, turkey, game birds |
| `Fish & Seafood` | All fish, shellfish, dried fish |
| `Grains` | Rice, maize, sorghum, wheat and their flours |
| `Legumes` | Beans, lentils, peas, groundnuts |
| `Dairy & Eggs` | Milk, cheese, yogurt, eggs |
| `Fats & Oils` | All cooking fats and oils |
| `Spices & Seasonings` | Spices, dried herbs, sauces, condiments |
| `Liquids` | Broths, juices, extracts, syrups |
| `Other` | Everything else (nuts, sweeteners, pantry staples) |

---

## Ingredient Roles (in dish_ingredients.csv)

| Role | Meaning |
|------|---------|
| `primary` | The signature ingredient — the dish is named after it or built around it. Every dish must have exactly one. |
| `required` | Needed to make the dish. Without it, the dish is incomplete. |
| `optional` | Adds flavour or texture but the dish works without it. |
| `garnish` | Served on top or alongside but not cooked into the dish. |

---

## Staple Flag

Set `is_staple = true` for ingredients that are almost always in a kitchen:

- `salt`, `water`, `cooking oil`, `vegetable oil`, `onion`, `garlic`, `tomato`

Do **not** mark protein-rich ingredients as staples even if common (e.g. `beef` is not a staple).

---

## Dish Fields

| Field | Format | Example |
|-------|--------|---------|
| `slug` | Slug rules above | `nyama-choma` |
| `name_en` | Title case | `Nyama Choma` |
| `name_sw` | Title case | `Nyama Choma` |
| `description` | One sentence, no period | `Kenyan grilled goat meat marinated with garlic and lemon` |
| `meal_type` | `breakfast` / `lunch` / `dinner` / `snack` / `dessert` / `beverage` | `dinner` |
| `course` | `starter` / `main` / `side` / `dessert` / `snack` / `beverage` | `main` |
| `spice_level` | Integer 0–5 | `3` |
| `difficulty` | `easy` / `medium` / `hard` | `medium` |
| `status` | `draft` / `reviewed` / `verified` / `archived` | `draft` |

### Nutrition fields

All nutrition is per-serving (not per 100g). Approximate values are acceptable for `draft` status.  
Use `0` for unknown values — do not leave blank.

---

## Pairings (pairings.csv)

| Field | Rules |
|-------|-------|
| `dish_slug` | Must exist in `dishes.csv` |
| `paired_dish_slug` | Must exist in `dishes.csv`, OR leave blank and use `paired_label` |
| `paired_label` | Free text for non-dish pairings (e.g. "beer", "chapati") |
| `pairing_type` | `side` / `drink` / `dessert` / `complementary` |
| `strength` | Integer 1–5 (5 = essential, 1 = occasional) |
| `note` | Optional explanation |

Do not leave both `paired_dish_slug` and `paired_label` blank.

---

## Substitutions (substitutions.csv)

| Field | Rules |
|-------|-------|
| `ingredient_slug` | Must exist in `ingredients.csv` |
| `substitute_slug` | Must exist in `ingredients.csv` |
| `ratio` | Decimal. `1.0` = same quantity. `0.5` = use half as much. |
| `quality` | `great` (works perfectly) / `ok` (works with adjustment) / `emergency` (last resort) |
| `context_dish_slug` | Optional — slug of the dish this sub is specifically for |
| `note` | Human-readable explanation of the substitution |

---

## Golden Set (golden_set_v0.json)

- IDs are sequential: `G01`, `G02`, … `G99`, `G100`, `G101`, …
- `inputs` are exactly what a user would type (not pre-normalised)
- `matched_slugs` must use real slugs from `ingredients.csv`
- `method_for_input` values: `exact_name`, `exact_alias`, `fuzzy`
- Test edge cases: Swahili input, typos, quantity prefixes, UPPERCASE, plurals
- Pass criterion: 95%+ of cases must pass on every CI run

---

## Adding New Data

1. Add rows to the relevant CSV.
2. Run the QA report: `python manage.py qa_report --fail-on-critical`
3. Run the golden set: `python manage.py run_golden_set`
4. Ensure no duplicate slugs: `python manage.py qa_report` will flag them.
5. For large batches (50+ rows), write a generation script in `scripts/` following the `expand_data_e44.py` / `expand_data_e45.py` pattern.
