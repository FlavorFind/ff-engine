"""
E45 — Final seed expansion script.
Targets:
  - Dishes: 300+ (currently 281, need +19)
  - Pairings: 150 (currently 121, need +29; also fix 80 column-shifted rows)
  - Substitutions: 200 (currently 111, need +89)
  - Ingredients: 800+ (already 878, no action needed)

Run: python3 scripts/expand_data_e45.py
"""

from __future__ import annotations

import csv
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Fix pairings column shift ─────────────────────────────────────────────────
# Rows 42-121 have: paired_label=pairing_type, pairing_type=strength, strength=note
# Fix: shift those fields left and clear note (set to '')


def fix_pairings():
    path = os.path.join(BASE, "data/seeds/pairings.csv")
    fixed = []
    with open(path) as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for r in reader:
            if r["strength"] and not r["strength"].isdigit():
                # Column-shifted row: paired_label→pairing_type, pairing_type→strength, strength→note
                fixed.append(
                    {
                        "dish_slug": r["dish_slug"],
                        "paired_dish_slug": r["paired_dish_slug"],
                        "paired_label": "",
                        "pairing_type": r["paired_label"],
                        "strength": r["pairing_type"],
                        "note": r["strength"],
                    }
                )
            else:
                fixed.append(dict(r))

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(fixed)
    print(f"Fixed {sum(1 for r in fixed if r.get('note'))} column-shifted pairing rows")
    return len(fixed)


# ── New dishes (+19 to reach 300) ─────────────────────────────────────────────
# Format: slug, name_en, description, meal_type, course, spice_level, difficulty,
#         prep_min, cook_min, servings, calories, protein_g, fat_g, carbs_g,
#         fiber_g, sugar_g, cholesterol_mg, sodium_mg, keywords, status

NEW_DISHES = [
    (
        "west-african-jollof-rice",
        "West African Jollof Rice",
        "Tomato-based spiced rice with chicken and vegetables",
        "dinner",
        "main",
        "3",
        "medium",
        "20",
        "50",
        "6",
        "420",
        "22",
        "12",
        "58",
        "3",
        "5",
        "55",
        "480",
        "WestAfrican|Rice|Tomato|Chicken",
        "draft",
    ),
    (
        "ghanaian-fufu-light-soup",
        "Ghanaian Fufu with Light Soup",
        "Pounded cassava and plantain with spiced chicken broth",
        "dinner",
        "main",
        "3",
        "hard",
        "30",
        "60",
        "4",
        "380",
        "24",
        "10",
        "55",
        "4",
        "3",
        "65",
        "440",
        "Ghanaian|Fufu|Soup|Chicken",
        "draft",
    ),
    (
        "nigerian-egusi-soup",
        "Nigerian Egusi Soup",
        "Rich melon seed soup with leafy greens and stockfish",
        "dinner",
        "main",
        "3",
        "medium",
        "20",
        "45",
        "6",
        "420",
        "28",
        "22",
        "18",
        "5",
        "3",
        "60",
        "520",
        "Nigerian|Egusi|Soup|Melon",
        "draft",
    ),
    (
        "senegalese-thieboudienne",
        "Senegalese Thieboudienne",
        "Senegalese fish and rice cooked in tomato sauce",
        "dinner",
        "main",
        "2",
        "hard",
        "30",
        "60",
        "6",
        "400",
        "26",
        "10",
        "52",
        "4",
        "4",
        "55",
        "500",
        "Senegalese|Fish|Rice|Tomato",
        "draft",
    ),
    (
        "moroccan-lamb-tagine",
        "Moroccan Lamb Tagine",
        "Slow-cooked lamb with apricots, almonds and ras el hanout",
        "dinner",
        "main",
        "2",
        "medium",
        "20",
        "90",
        "4",
        "480",
        "35",
        "22",
        "32",
        "4",
        "18",
        "95",
        "480",
        "Moroccan|Lamb|Tagine|Apricot",
        "draft",
    ),
    (
        "moroccan-chicken-tagine",
        "Moroccan Chicken Tagine",
        "Chicken with preserved lemon, olives and aromatic spices",
        "dinner",
        "main",
        "2",
        "medium",
        "20",
        "60",
        "4",
        "380",
        "30",
        "16",
        "18",
        "3",
        "4",
        "80",
        "520",
        "Moroccan|Chicken|Tagine|Lemon",
        "draft",
    ),
    (
        "egyptian-koshari",
        "Egyptian Koshari",
        "Layered lentils, rice, pasta with crispy onions and tomato sauce",
        "lunch",
        "main",
        "2",
        "medium",
        "20",
        "45",
        "4",
        "420",
        "14",
        "8",
        "72",
        "8",
        "6",
        "0",
        "480",
        "Egyptian|Vegetarian|Rice|Lentils",
        "draft",
    ),
    (
        "south-african-bobotie",
        "South African Bobotie",
        "Spiced minced beef bake with egg custard topping",
        "dinner",
        "main",
        "2",
        "medium",
        "20",
        "45",
        "4",
        "420",
        "28",
        "24",
        "22",
        "2",
        "8",
        "120",
        "500",
        "SouthAfrican|Beef|Bake|Spiced",
        "draft",
    ),
    (
        "south-african-boerewors-roll",
        "South African Boerewors Roll",
        "Grilled boerewors sausage in a soft roll with chakalaka",
        "lunch",
        "snack",
        "2",
        "easy",
        "10",
        "20",
        "2",
        "380",
        "22",
        "20",
        "28",
        "2",
        "5",
        "60",
        "540",
        "SouthAfrican|Sausage|Roll|Grilled",
        "draft",
    ),
    (
        "cameroonian-ndole",
        "Cameroonian Ndole",
        "Bitter leaf stew with groundnuts, prawns and beef",
        "dinner",
        "main",
        "2",
        "hard",
        "30",
        "60",
        "4",
        "380",
        "28",
        "18",
        "20",
        "6",
        "3",
        "75",
        "440",
        "Cameroonian|BitterLeaf|Groundnut|Stew",
        "draft",
    ),
    (
        "ivorian-attiéké-fish",
        "Ivorian Attiéké with Fish",
        "Fermented cassava couscous with grilled tilapia and onion sauce",
        "lunch",
        "main",
        "2",
        "medium",
        "15",
        "30",
        "2",
        "350",
        "28",
        "10",
        "42",
        "3",
        "4",
        "55",
        "380",
        "Ivorian|Cassava|Fish|Coastal",
        "draft",
    ),
    (
        "kenyan-mahindi-choma",
        "Kenyan Mahindi Choma",
        "Roasted maize on the cob, a popular Kenyan street snack",
        "snack",
        "snack",
        "1",
        "easy",
        "5",
        "20",
        "2",
        "120",
        "4",
        "1",
        "26",
        "3",
        "5",
        "0",
        "5",
        "Kenyan|Maize|Roasted|Snack",
        "draft",
    ),
    (
        "kenyan-bhajia-ndizi",
        "Kenyan Bhajia ya Ndizi",
        "Plantain fritters spiced with cumin and coriander",
        "snack",
        "snack",
        "2",
        "easy",
        "10",
        "15",
        "4",
        "220",
        "3",
        "10",
        "30",
        "3",
        "8",
        "0",
        "180",
        "Kenyan|Plantain|Fritter|Snack",
        "draft",
    ),
    (
        "kenyan-vitumbua",
        "Kenyan Vitumbua",
        "Coconut rice pancakes, a coastal breakfast staple",
        "breakfast",
        "snack",
        "1",
        "medium",
        "15",
        "20",
        "4",
        "280",
        "5",
        "8",
        "44",
        "2",
        "10",
        "20",
        "120",
        "Kenyan|Coconut|Rice|Breakfast",
        "draft",
    ),
    (
        "kenyan-samosa-ya-viazi",
        "Kenyan Samosa ya Viazi",
        "Potato-filled pastry parcels, deep fried until golden",
        "snack",
        "snack",
        "2",
        "medium",
        "30",
        "20",
        "6",
        "280",
        "5",
        "14",
        "34",
        "2",
        "2",
        "0",
        "320",
        "Kenyan|Potato|Samosa|Fried",
        "draft",
    ),
    (
        "tanzanian-supu-ya-ndizi",
        "Tanzanian Supu ya Ndizi",
        "Green banana and beef soup from the Kilimanjaro region",
        "lunch",
        "starter",
        "2",
        "easy",
        "15",
        "40",
        "4",
        "220",
        "14",
        "6",
        "28",
        "4",
        "5",
        "35",
        "380",
        "Tanzanian|Banana|Beef|Soup",
        "draft",
    ),
    (
        "ethiopian-shiro-wat",
        "Ethiopian Shiro Wat",
        "Spiced chickpea flour stew with niter kibbeh and berbere",
        "dinner",
        "main",
        "3",
        "easy",
        "10",
        "25",
        "4",
        "280",
        "14",
        "10",
        "34",
        "6",
        "4",
        "0",
        "380",
        "Ethiopian|Chickpea|Vegetarian|Stew",
        "draft",
    ),
    (
        "ethiopian-tibs",
        "Ethiopian Tibs",
        "Pan-fried beef or lamb with rosemary, onions and jalapeño",
        "dinner",
        "main",
        "3",
        "easy",
        "15",
        "20",
        "4",
        "360",
        "30",
        "20",
        "8",
        "2",
        "2",
        "85",
        "420",
        "Ethiopian|Beef|Fried|Spiced",
        "draft",
    ),
    (
        "somali-bariis-iskukaris",
        "Somali Bariis Iskukaris",
        "Fragrant rice with raisins, cumin and cinnamon, served with goat",
        "dinner",
        "main",
        "2",
        "medium",
        "20",
        "50",
        "6",
        "420",
        "25",
        "12",
        "58",
        "2",
        "8",
        "55",
        "440",
        "Somali|Rice|Goat|Spiced",
        "draft",
    ),
]


# ── New pairings (+29 to reach 150) ──────────────────────────────────────────
# Format: dish_slug, paired_dish_slug, paired_label, pairing_type, strength, note

NEW_PAIRINGS = [
    # West African new dishes
    (
        "west-african-jollof-rice",
        "fried-plantain",
        "",
        "side",
        "5",
        "The classic West African pairing",
    ),
    ("west-african-jollof-rice", "coleslaw", "", "side", "4", "Cool creamy slaw with spiced rice"),
    (
        "west-african-jollof-rice",
        "",
        "Chapman drink",
        "drink",
        "3",
        "Nigerian citrus drink with jollof",
    ),
    (
        "ghanaian-fufu-light-soup",
        "kelewele",
        "",
        "side",
        "4",
        "Spiced plantain with the light soup",
    ),
    ("nigerian-egusi-soup", "eba", "", "side", "5", "Cassava dough scoops up the egusi"),
    ("nigerian-egusi-soup", "pounded-yam", "", "side", "5", "Classic pairing for egusi soup"),
    ("moroccan-lamb-tagine", "couscous", "", "side", "5", "Couscous soaks up the tagine sauce"),
    (
        "moroccan-lamb-tagine",
        "",
        "Moroccan mint tea",
        "drink",
        "4",
        "Sweet mint tea after a tagine",
    ),
    ("moroccan-chicken-tagine", "couscous", "", "side", "5", "Couscous with chicken tagine"),
    ("moroccan-chicken-tagine", "", "harissa flatbread", "side", "4", "Bread to mop up the sauce"),
    (
        "egyptian-koshari",
        "",
        "tomato vinegar sauce",
        "side",
        "5",
        "Tangy sauce is essential for koshari",
    ),
    ("south-african-bobotie", "yellow-rice", "", "side", "5", "Turmeric rice with bobotie"),
    ("south-african-bobotie", "", "chutney", "side", "4", "Fruit chutney cuts the richness"),
    ("cameroonian-ndole", "fried-plantain", "", "side", "5", "Classic Central African pairing"),
    ("cameroonian-ndole", "miondo", "", "side", "4", "Cassava sticks with the leaf stew"),
    ("ivorian-attiéké-fish", "", "alloco", "side", "4", "Fried plantain alongside the fish"),
    # Ethiopian new dishes
    ("ethiopian-shiro-wat", "injera", "", "side", "5", "Shiro is always served on injera"),
    ("ethiopian-shiro-wat", "ayib", "", "side", "4", "Fresh cheese cools the spiced stew"),
    ("ethiopian-tibs", "injera", "", "side", "5", "Tibs always served with injera"),
    ("ethiopian-tibs", "", "tej", "drink", "4", "Honey wine with pan-fried meat"),
    (
        "somali-bariis-iskukaris",
        "",
        "basmati salad",
        "side",
        "3",
        "Light salad alongside fragrant rice",
    ),
    ("somali-bariis-iskukaris", "", "Somali tea", "drink", "4", "Spiced tea after the rice dish"),
    # Kenyan new snacks / breakfast
    (
        "kenyan-mahindi-choma",
        "",
        "tamarind sauce",
        "side",
        "4",
        "Tangy tamarind with roasted maize",
    ),
    ("kenyan-vitumbua", "masala-chai", "", "drink", "5", "Classic coastal morning pairing"),
    ("kenyan-vitumbua", "", "mango chutney", "side", "3", "Sweet chutney with coconut pancakes"),
    ("kenyan-samosa-ya-viazi", "masala-chai", "", "drink", "5", "The classic samosa-tea pairing"),
    (
        "kenyan-samosa-ya-viazi",
        "tamarind-juice-ukwaju",
        "",
        "drink",
        "4",
        "Tamarind cuts through the fried pastry",
    ),
    ("kenyan-bhajia-ndizi", "masala-chai", "", "drink", "4", "Tea with plantain fritters"),
    ("tanzanian-supu-ya-ndizi", "ugali", "", "side", "4", "Stiff porridge with the banana soup"),
]


# ── New substitutions (+89 to reach 200) ──────────────────────────────────────
# Format: ingredient_slug, substitute_slug, ratio, quality, context_dish_slug, note

NEW_SUBSTITUTIONS = [
    # Oils and fats
    ("olive-oil", "sunflower-oil", "1.0", "great", "", "Neutral oil works in any recipe"),
    ("olive-oil", "avocado-oil", "1.0", "great", "", "Same fat profile, similar flavour"),
    ("butter", "margarine", "1.0", "ok", "", "Margarine melts like butter"),
    ("butter", "coconut-oil", "0.8", "ok", "", "Use slightly less — coconut oil is richer"),
    ("ghee", "butter", "1.0", "great", "", "Butter is the base of ghee"),
    ("ghee", "coconut-oil", "1.0", "ok", "", "Similar high smoke point"),
    ("lard", "beef-tallow", "1.0", "great", "", "Same animal fat, same smoke point"),
    ("vegetable-oil", "sunflower-oil", "1.0", "great", "", "Direct swap"),
    ("sesame-oil", "walnut-oil", "1.0", "ok", "", "Nutty flavour but less intense"),
    ("palm-oil", "coconut-oil", "1.0", "ok", "", "Similar tropical fat"),
    # Dairy
    ("milk", "oat-milk", "1.0", "ok", "", "Works in cooking and baking"),
    ("milk", "soy-milk", "1.0", "ok", "", "Neutral flavour, good protein"),
    ("milk", "evaporated-milk", "0.5", "ok", "", "Dilute 1:1 with water before using"),
    ("cream", "coconut-cream", "1.0", "ok", "", "Richer and slightly sweet"),
    ("cream", "evaporated-milk", "1.0", "ok", "", "Less fat, more liquid"),
    ("yogurt", "sour-cream", "1.0", "great", "", "Same tang and texture"),
    ("yogurt", "labneh", "0.75", "great", "", "Labneh is thicker — use less"),
    ("greek-yogurt", "labneh", "1.0", "great", "", "Almost identical consistency"),
    ("feta-cheese", "halloumi", "1.0", "ok", "", "Halloumi is less salty, holds shape when cooked"),
    ("mozzarella", "provolone", "1.0", "ok", "", "Melts similarly but stronger flavour"),
    ("parmesan", "pecorino-romano", "1.0", "great", "", "Slightly saltier but the same function"),
    ("ricotta", "cottage-cheese", "1.0", "ok", "", "Blend cottage cheese for smoother texture"),
    ("cheddar-cheese", "gouda", "1.0", "ok", "", "Milder but melts well"),
    ("heavy-cream", "coconut-cream", "1.0", "ok", "", "Works in soups and curries"),
    # Eggs
    ("eggs", "silken-tofu", "0.25", "ok", "", "25g tofu per egg in baking"),
    ("eggs", "flaxseed", "0.15", "ok", "", "1 tbsp ground flax + 3 tbsp water per egg"),
    ("egg-yolk", "cashew-cream", "1.0", "ok", "", "Richness without cholesterol"),
    # Proteins
    ("chicken", "turkey", "1.0", "great", "", "Same cooking times, slightly drier"),
    ("chicken", "rabbit", "1.0", "ok", "", "Lean white meat, similar texture"),
    ("beef", "lamb", "1.0", "great", "", "Richer flavour, same cooking methods"),
    ("beef", "bison", "1.0", "great", "", "Leaner but same texture"),
    ("pork", "chicken", "1.0", "ok", "", "Adjust seasonings — chicken is milder"),
    ("lamb", "goat-meat", "1.0", "great", "", "Similar gamey flavour and texture"),
    ("goat-meat", "lamb", "1.0", "great", "", "Lamb is slightly milder"),
    ("tilapia", "catfish", "1.0", "great", "", "Same freshwater fish texture"),
    ("tilapia", "bream", "1.0", "great", "", "Similar mild white fish"),
    ("salmon", "trout", "1.0", "great", "", "Same omega-3 rich family"),
    ("tuna", "skipjack-tuna", "1.0", "great", "", "Same family, similar flavour"),
    ("prawns", "shrimp", "1.0", "great", "", "Direct swap by weight"),
    ("beef-mince", "turkey-mince", "1.0", "ok", "", "Leaner, add extra oil"),
    ("minced-beef", "minced-pork", "1.0", "ok", "", "Slightly fattier"),
    ("chicken-pieces", "duck", "1.0", "ok", "", "Duck is richer — reduce oil"),
    ("beef-liver", "chicken-liver", "1.0", "great", "", "Milder flavour, same technique"),
    # Grains and starches
    ("wheat-flour", "rice-flour", "1.0", "ok", "", "Gluten-free option — texture differs"),
    ("wheat-flour", "almond-flour", "0.75", "ok", "", "Denser result — use less"),
    ("rice", "quinoa", "1.0", "ok", "", "Higher protein, slightly nuttier"),
    ("rice", "cauliflower-rice", "1.0", "ok", "", "Low-carb option"),
    ("maize-flour", "sorghum-flour", "1.0", "ok", "", "Slightly earthier flavour"),
    ("maize-flour", "millet-flour", "1.0", "ok", "", "Lighter texture"),
    ("sorghum-flour", "millet-flour", "1.0", "great", "", "Very similar ancient grains"),
    ("bread-flour", "all-purpose-flour", "1.0", "ok", "", "Slightly less gluten"),
    ("semolina", "polenta", "1.0", "ok", "", "Coarser grind, similar corn base"),
    ("couscous", "bulgur", "1.0", "great", "", "Same quick-cook grain texture"),
    ("bulgur", "couscous", "1.0", "ok", "", "Slightly nuttier"),
    ("pasta", "rice-noodles", "1.0", "ok", "", "Gluten-free option for noodle dishes"),
    ("rice-noodles", "glass-noodles", "1.0", "ok", "", "Similar delicate noodle"),
    ("cornstarch", "arrowroot", "1.0", "great", "", "Same thickening power"),
    ("cornstarch", "tapioca", "1.0", "ok", "", "Works but produces chewier texture"),
    # Legumes
    ("chickpeas", "white-beans", "1.0", "great", "", "Same creamy texture when cooked"),
    ("chickpeas", "lentils", "1.0", "ok", "", "Softer texture, shorter cook time"),
    ("black-beans", "kidney-beans", "1.0", "great", "", "Same hearty bean texture"),
    ("lentils", "split-peas", "1.0", "great", "", "Same quick-cook legume"),
    ("red-lentils", "split-red-lentils", "1.0", "great", "", "Essentially the same ingredient"),
    ("kidney-beans", "borlotti-beans", "1.0", "great", "", "Similar size and texture"),
    ("pigeon-peas", "cowpeas", "1.0", "great", "", "Same East African legume family"),
    # Vegetables
    ("spinach", "kale", "1.0", "ok", "", "Kale needs longer cooking"),
    ("spinach", "Swiss-chard", "1.0", "great", "", "Same leafy green family"),
    ("collard-greens", "kale", "1.0", "great", "", "Similar tough leafy greens"),
    ("potato", "sweet-potato", "1.0", "ok", "", "Sweeter result — adjust seasoning"),
    ("sweet-potato", "butternut-squash", "1.0", "ok", "", "Similar sweetness and texture"),
    ("carrot", "parsnip", "1.0", "ok", "", "Parsnip is earthier and sweeter"),
    ("onion", "shallots", "0.5", "great", "", "Shallots are more concentrated"),
    ("garlic", "garlic-powder", "0.1", "ok", "", "1/8 tsp powder per fresh clove"),
    ("fresh-ginger", "dried-ginger", "0.25", "ok", "", "Use 1/4 tsp dried per 1 inch fresh"),
    ("tomato", "canned-tomatoes", "1.0", "great", "", "Use same weight of canned"),
    ("tomato", "tomato-paste", "0.2", "ok", "", "Dilute paste 3:1 with water"),
    ("lemon", "lime", "1.0", "great", "", "Same acidity — lime is slightly more tart"),
    ("lime", "lemon", "1.0", "great", "", "Lemon is slightly milder"),
    ("green-pepper", "red-pepper", "1.0", "ok", "", "Red pepper is sweeter when raw"),
    ("pumpkin", "butternut-squash", "1.0", "great", "", "Same orange flesh squash family"),
    ("cassava", "potato", "1.0", "ok", "", "Adjust cook time — cassava takes longer"),
    ("plantain", "banana", "1.0", "ok", "", "Use underripe banana as a starchy sub"),
    # Spices and seasonings
    ("cumin", "caraway-seeds", "1.0", "ok", "", "Caraway is earthier but similar"),
    ("coriander-powder", "caraway-seeds", "0.5", "ok", "", "Milder — use half"),
    ("turmeric", "saffron", "0.1", "ok", "", "Saffron gives colour but different flavour"),
    ("paprika", "cayenne-pepper", "0.25", "ok", "", "Much hotter — use a quarter"),
    ("fresh-chili", "dried-chili", "0.33", "ok", "", "Use 1/3 as much dried"),
    ("coconut-milk", "cream", "1.0", "ok", "", "Dairy cream in non-vegan recipes"),
    ("soy-sauce", "tamari", "1.0", "great", "", "Tamari is gluten-free and richer"),
    ("fish-sauce", "soy-sauce", "0.75", "ok", "", "Use 3/4 — less pungent but salty"),
    ("tamarind", "lemon-juice", "2.0", "ok", "", "Double the lemon — less sour than tamarind"),
    ("coconut-cream", "heavy-cream", "1.0", "ok", "", "Works in non-tropical recipes"),
]


def main():
    # 1. Fix pairings column shift
    fix_pairings()

    # 2. Add new dishes
    dish_path = os.path.join(BASE, "data/seeds/dishes.csv")
    with open(dish_path) as f:
        existing_dish_slugs = {row["slug"] for row in csv.DictReader(f)}

    new_dishes = [r for r in NEW_DISHES if r[0] not in existing_dish_slugs]
    if new_dishes:
        with open(dish_path, "a", newline="") as f:
            writer = csv.writer(f)
            for row in new_dishes:
                writer.writerow(row)
        total = len(existing_dish_slugs) + len(new_dishes)
        print(f"Added {len(new_dishes)} dishes (total: {total})")
    else:
        print("No new dishes to add")

    # 3. Add new pairings (after fix, check we hit 150)
    pairing_path = os.path.join(BASE, "data/seeds/pairings.csv")
    with open(pairing_path) as f:
        reader = csv.DictReader(f)
        existing_pairings = list(reader)
    existing_pairing_keys = {
        (r["dish_slug"], r["paired_dish_slug"], r["paired_label"]) for r in existing_pairings
    }

    new_pairings_to_add = []
    for row in NEW_PAIRINGS:
        key = (row[0], row[1], row[2])
        if key not in existing_pairing_keys:
            new_pairings_to_add.append(row)

    if new_pairings_to_add:
        with open(pairing_path, "a", newline="") as f:
            writer = csv.writer(f)
            for row in new_pairings_to_add:
                writer.writerow(row)
        total = len(existing_pairings) + len(new_pairings_to_add)
        print(f"Added {len(new_pairings_to_add)} pairings (total: {total})")
    else:
        print("No new pairings to add")

    # 4. Add new substitutions
    sub_path = os.path.join(BASE, "data/seeds/substitutions.csv")
    with open(sub_path) as f:
        existing_subs = list(csv.DictReader(f))
    existing_sub_keys = {(r["ingredient_slug"], r["substitute_slug"]) for r in existing_subs}

    new_subs_to_add = []
    for row in NEW_SUBSTITUTIONS:
        key = (row[0], row[1])
        if key not in existing_sub_keys:
            new_subs_to_add.append(row)

    if new_subs_to_add:
        with open(sub_path, "a", newline="") as f:
            writer = csv.writer(f)
            for row in new_subs_to_add:
                writer.writerow(row)
        total = len(existing_subs) + len(new_subs_to_add)
        print(f"Added {len(new_subs_to_add)} substitutions (total: {total})")
    else:
        print("No new substitutions to add")

    # 5. Validate all dish ingredient references
    with open(os.path.join(BASE, "data/seeds/ingredients.csv")) as f:
        ing_slugs = {r["slug"] for r in csv.DictReader(f)}
    with open(os.path.join(BASE, "data/seeds/dishes.csv")) as f:
        dish_slugs_all = {r["slug"] for r in csv.DictReader(f)}
    with open(os.path.join(BASE, "data/seeds/dish_ingredients.csv")) as f:
        links = list(csv.DictReader(f))

    missing_ings = [r for r in links if r["ingredient_slug"] not in ing_slugs]
    missing_dishes = [r for r in links if r["dish_slug"] not in dish_slugs_all]
    if missing_ings:
        print(f"WARNING: {len(missing_ings)} links reference missing ingredients")
        for r in missing_ings[:5]:
            print(f"  {r['dish_slug']} -> {r['ingredient_slug']}")
    if missing_dishes:
        print(f"WARNING: {len(missing_dishes)} links reference missing dishes")
    if not missing_ings and not missing_dishes:
        print("All dish-ingredient links valid ✓")

    # 6. Final summary
    print("\n=== E45 Final Counts ===")
    with open(os.path.join(BASE, "data/seeds/ingredients.csv")) as f:
        print(f"Ingredients: {sum(1 for _ in csv.DictReader(f))}")
    with open(os.path.join(BASE, "data/seeds/dishes.csv")) as f:
        print(f"Dishes:      {sum(1 for _ in csv.DictReader(f))}")
    with open(os.path.join(BASE, "data/seeds/pairings.csv")) as f:
        print(f"Pairings:    {sum(1 for _ in csv.DictReader(f))}")
    with open(os.path.join(BASE, "data/seeds/substitutions.csv")) as f:
        print(f"Substitutions: {sum(1 for _ in csv.DictReader(f))}")


if __name__ == "__main__":
    main()
