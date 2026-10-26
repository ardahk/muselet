"""Seed content for the LH-v1 local fixture sites (lead-authored eval content).

Fictional, deterministic data. Graders in `graders.py` rely on the ids and values here,
so changing an entry changes the benchmark: bump the suite version in `evals/lh_v1.jsonl`.
"""

def _p(pid, name, category, price, size, desc, tags=()):
    return {"id": pid, "name": name, "category": category, "price": price, "size": size,
            "desc": desc, "tags": list(tags)}


PRODUCTS = [
    # Produce
    _p("banana", "Banana", "Produce", "0.29", "each", "A single ripe yellow banana.", ["fruit", "bananas"]),
    _p("banana-organic", "Organic Banana", "Produce", "0.39", "each", "A single organic banana.",
       ["fruit", "bananas"]),
    _p("apples-gala", "Gala Apples, 3 lb bag", "Produce", "4.99", "3 lb", "Crisp, sweet gala apples.",
       ["fruit", "apple"]),
    _p("strawberries", "Strawberries, 1 lb", "Produce", "3.99", "1 lb", "Fresh strawberries.", ["fruit", "berries"]),
    _p("avocados", "Avocados, 4 count", "Produce", "5.49", "4 count", "Hass avocados.", ["fruit"]),
    _p("spinach", "Baby Spinach, 5 oz", "Produce", "3.29", "5 oz", "Pre-washed baby spinach.", ["greens", "salad"]),
    # Dairy & Eggs
    _p("milk-whole-gal", "Whole Milk, 1 gallon", "Dairy & Eggs", "4.29", "1 gallon", "Vitamin D whole milk.",
       ["milk"]),
    _p("milk-whole-half", "Whole Milk, half gallon", "Dairy & Eggs", "2.59", "half gallon", "Vitamin D whole milk.",
       ["milk"]),
    _p("milk-2pct-gal", "2% Reduced Fat Milk, 1 gallon", "Dairy & Eggs", "4.19", "1 gallon", "Reduced fat milk.",
       ["milk"]),
    _p("milk-oat", "Oat Milk, 64 oz", "Dairy & Eggs", "4.79", "64 oz", "Plant-based oat milk.", ["milk", "dairy-free"]),
    _p("eggs-large-dozen", "Large Eggs, dozen", "Dairy & Eggs", "3.49", "12 count", "Grade A large white eggs.",
       ["eggs"]),
    _p("eggs-large-18", "Large Eggs, 18 count", "Dairy & Eggs", "4.99", "18 count", "Grade A large white eggs.",
       ["eggs"]),
    _p("eggs-brown-dozen", "Cage-Free Brown Eggs, dozen", "Dairy & Eggs", "4.49", "12 count", "Cage-free brown eggs.",
       ["eggs"]),
    _p("butter-unsalted", "Unsalted Butter, 1 lb", "Dairy & Eggs", "4.99", "1 lb", "Four sticks of unsalted butter.",
       ["butter"]),
    _p("butter-salted", "Salted Butter, 1 lb", "Dairy & Eggs", "4.89", "1 lb", "Four sticks of salted butter.",
       ["butter"]),
    _p("yogurt-greek", "Greek Yogurt, 32 oz", "Dairy & Eggs", "5.99", "32 oz", "Plain Greek yogurt.", ["yogurt"]),
    _p("cheddar", "Sharp Cheddar Cheese, 8 oz", "Dairy & Eggs", "3.79", "8 oz", "Aged sharp cheddar.", ["cheese"]),
    # Bakery
    _p("bread-sourdough", "Sourdough Loaf", "Bakery", "5.49", "24 oz", "Naturally leavened sourdough.", ["bread"]),
    _p("bread-wheat", "Whole Wheat Bread", "Bakery", "3.29", "20 oz", "Sliced whole wheat bread.", ["bread"]),
    _p("bagels", "Plain Bagels, 6 count", "Bakery", "4.29", "6 count", "New York style bagels.", ["bread"]),
    # Pantry
    _p("pancake-mix", "Pancake Mix, 32 oz", "Pantry", "3.99", "32 oz", "Just add water, eggs and milk.",
       ["pancakes", "breakfast"]),
    _p("maple-syrup", "Maple Syrup, 12 oz", "Pantry", "7.49", "12 oz", "Pure grade A maple syrup.",
       ["pancakes", "breakfast"]),
    _p("flour", "All-Purpose Flour, 5 lb", "Pantry", "3.89", "5 lb", "Unbleached all-purpose flour.", ["baking"]),
    # Coffee & Tea (beans-breakfast is the cheapest whole-bean product by price and by price per ounce;
    # ground and instant coffee are cheaper decoys that are not beans)
    _p("beans-house", "House Blend Coffee Beans, 12 oz", "Coffee & Tea", "8.99", "12 oz",
       "Medium roast whole bean coffee.", ["coffee", "whole bean"]),
    _p("beans-dark", "Dark Roast Coffee Beans, 12 oz", "Coffee & Tea", "9.49", "12 oz",
       "Dark roast whole bean coffee.", ["coffee", "whole bean"]),
    _p("beans-colombian", "Colombian Coffee Beans, 2 lb", "Coffee & Tea", "19.99", "2 lb",
       "Medium roast Colombian whole beans.", ["coffee", "whole bean"]),
    _p("beans-ethiopia", "Ethiopia Single-Origin Coffee Beans, 12 oz", "Coffee & Tea", "13.99", "12 oz",
       "Light roast single-origin whole beans.", ["coffee", "whole bean"]),
    _p("beans-breakfast", "Breakfast Blend Coffee Beans, 12 oz", "Coffee & Tea", "6.79", "12 oz",
       "Light, bright whole bean breakfast blend.", ["coffee", "whole bean"]),
    _p("ground-house", "House Blend Ground Coffee, 12 oz", "Coffee & Tea", "7.49", "12 oz",
       "Medium roast, pre-ground.", ["coffee", "ground"]),
    _p("coffee-instant", "Instant Coffee, 8 oz", "Coffee & Tea", "5.99", "8 oz", "Freeze-dried instant coffee.",
       ["coffee", "instant"]),
    _p("coffee-filters", "Coffee Filters, 100 count", "Coffee & Tea", "3.49", "100 count",
       "Basket-style paper coffee filters.", ["coffee", "filter"]),
    _p("tea-green", "Green Tea, 20 bags", "Coffee & Tea", "3.99", "20 bags", "Japanese sencha green tea.", ["tea"]),
    # Household
    _p("batt-aa-4", "AA Batteries, 4 pack", "Household", "5.99", "4 pack", "Alkaline AA batteries.",
       ["battery", "double a"]),
    _p("batt-aa-8", "AA Batteries, 8 pack", "Household", "9.99", "8 pack", "Alkaline AA batteries.",
       ["battery", "double a"]),
    _p("batt-aaa-4", "AAA Batteries, 4 pack", "Household", "5.49", "4 pack", "Alkaline AAA batteries.",
       ["battery", "triple a"]),
    _p("batt-aaa-8", "AAA Batteries, 8 pack", "Household", "9.49", "8 pack", "Alkaline AAA batteries.",
       ["battery", "triple a"]),
    _p("batt-aaa-recharge", "AAA Rechargeable Batteries, 4 pack", "Household", "14.99", "4 pack",
       "Pre-charged NiMH AAA batteries.", ["battery", "triple a", "rechargeable"]),
    _p("batt-9v", "9V Batteries, 2 pack", "Household", "7.99", "2 pack", "Alkaline 9 volt batteries.", ["battery"]),
    _p("paper-towels", "Paper Towels, 6 rolls", "Household", "12.99", "6 rolls", "Select-a-size paper towels.", []),
    _p("dish-soap", "Dish Soap, 22 oz", "Household", "3.49", "22 oz", "Lemon dish soap.", ["cleaning"]),
    # Electronics
    _p("usb-c-cable", "USB-C Cable, 6 ft", "Electronics", "9.99", "6 ft", "Braided USB-C to USB-C cable.", ["cable"]),
    _p("charger-20w", "20W USB-C Charger", "Electronics", "19.99", "1 count", "Compact 20 watt wall charger.",
       ["charger"]),
    _p("mouse-wireless", "Wireless Mouse", "Electronics", "24.99", "1 count", "Bluetooth wireless mouse.", ["mouse"]),
]

FEATURED = ["banana", "milk-whole-gal", "eggs-large-dozen", "beans-house", "batt-aa-4", "bread-sourdough"]


def _m(mid, from_name, from_addr, date, subject, body):
    return {"id": mid, "from_name": from_name, "from_addr": from_addr, "to": "you@muselet-mail.example",
            "date": date, "subject": subject, "body": body}


EMAILS = [
    _m("m1", "Harborline Bank", "alerts@harborline.example", "2026-10-02T08:00", "Your October statement is ready",
       "Your Harborline Bank statement is ready to view online. This is an automated message."),
    _m("m2", "Priya Patel", "priya.patel@northwind.example", "2026-10-15T11:20", "Team lunch next week",
       "Hi! Team lunch is on Wednesday, October 28 at 12:30 PM at Rosie's Diner. "
       "Let me know if you have any dietary restrictions.\n\nPriya"),
    _m("m3", "Sam Carter", "sam@example.com", "2026-10-16T16:05", "Notes from Tuesday",
       "Thanks for the chat on Tuesday. I attached my notes to the shared folder. Talk soon, Sam"),
    _m("m4", "Jon Snow", "jon.snow@winterfell.example", "2026-10-18T19:40", "Night's Watch schedule",
       "Your watch shifts for next week are Monday and Thursday, 6 PM to midnight.\n\nJon"),
    _m("m5", "Muselet Mart", "orders@muselet-mart.example", "2026-10-19T07:30", "Your order has shipped",
       "Good news: order #0987 has shipped and should arrive in 2 to 3 days."),
    _m("m6", "Arya Stark", "arya@winterfell.example", "2026-10-20T13:10", "Sword lessons?",
       "Are we still on for sword lessons this weekend? Arya"),
    _m("m7", "Priya Patel", "priya.patel@northwind.example", "2026-10-21T09:45", "Q4 offsite logistics",
       "Hi team,\n\nThe Q4 offsite is on Thursday, November 12. We start at 9:30 AM in the Harbor Room on the "
       "3rd floor of the Pier 9 building. Breakfast is provided.\n\nPlease RSVP by Friday.\n\nThanks,\nPriya"),
    _m("m8", "Lorepedia Weekly", "newsletter@lorepedia.example", "2026-10-22T06:00", "This week on Lorepedia",
       "Featured this week: the Lantern Festival of Lumen Harbor and the history of the Selwyn Isles."),
    _m("m9", "Dana Kim", "dana.kim@northwind.example", "2026-10-22T15:30", "Budget review moved",
       "The budget review moved to Monday at 2 PM. Same room as before. Dana"),
    _m("m10", "Sansa Stark", "sansa@winterfell.example", "2026-10-23T18:00", "Dinner Saturday",
       "Dinner at our place on Saturday at 7? Bring dessert if you can. Sansa"),
    _m("m11", "Jon Snow", "jon.snow@winterfell.example", "2026-10-24T21:15", "Are you ready for winter?",
       "The maesters say the long winter is almost here. Are you ready? Let me know.\n\nJon"),
    _m("m12", "GitHub", "noreply@github.example", "2026-10-25T10:02", "[muselet] New issue opened",
       "A new issue was opened in muselet: \"Planner loops on Premiere speed dialog\"."),
]


def _a(slug, title, infobox, body):
    return {"slug": slug, "title": title, "infobox": infobox, "body": body}


ARTICLES = [
    _a("lumen-harbor", "Lumen Harbor",
       [["Type", "Port city"], ["Region", "[[selwyn-isles|Selwyn Isles]]"], ["Founded", "1781"],
        ["Founder", "[[ines-calder|Ines Calder]]"], ["Population", "412,000 (2020)"]],
       ["Lumen Harbor is a port city on the western coast of the [[selwyn-isles|Selwyn Isles]]. It was founded in "
        "1781 by the navigator [[ines-calder|Ines Calder]], who sailed with her younger brother "
        "[[tomas-calder|Tomas Calder]].",
        "The city is known for the [[varn-spire|Varn Spire]], the [[calder-bridge|Calder Bridge]] and its annual "
        "[[lantern-festival|Lantern Festival]]. Its harbor is one of the busiest in the region."]),
    _a("ines-calder", "Ines Calder",
       [["Born", "14 March 1742, [[port-selwyn|Port Selwyn]]"], ["Died", "2 June 1809, Lumen Harbor"],
        ["Occupation", "Navigator, cartographer"], ["Known for", "Founding [[lumen-harbor|Lumen Harbor]]"]],
       ["Ines Calder was a navigator and cartographer from [[port-selwyn|Port Selwyn]]. She charted most of the "
        "western coast of the [[selwyn-isles|Selwyn Isles]] and founded [[lumen-harbor|Lumen Harbor]] in 1781.",
        "Her brother [[tomas-calder|Tomas Calder]] accompanied her on her later voyages. The "
        "[[calder-bridge|Calder Bridge]] is named after her."]),
    _a("tomas-calder", "Tomas Calder",
       [["Born", "1745, Port Selwyn"], ["Died", "1811"], ["Occupation", "Navigator"]],
       ["Tomas Calder was a navigator and the younger brother of [[ines-calder|Ines Calder]]. He served as "
        "co-navigator on the voyage that led to the founding of [[lumen-harbor|Lumen Harbor]]."]),
    _a("port-selwyn", "Port Selwyn",
       [["Type", "Town"], ["Region", "[[selwyn-isles|Selwyn Isles]]"], ["Population", "38,000 (2020)"]],
       ["Port Selwyn is the oldest town in the [[selwyn-isles|Selwyn Isles]] and the birthplace of the navigator "
        "[[ines-calder|Ines Calder]]."]),
    _a("selwyn-isles", "Selwyn Isles",
       [["Type", "Archipelago"], ["Largest city", "[[lumen-harbor|Lumen Harbor]]"], ["Islands", "14"]],
       ["The Selwyn Isles are an archipelago of fourteen islands. The largest city is [[lumen-harbor|Lumen Harbor]]; "
        "the oldest town is [[port-selwyn|Port Selwyn]]."]),
    _a("varn-spire", "Varn Spire",
       [["Type", "Observation tower"], ["Location", "[[lumen-harbor|Lumen Harbor]]"], ["Completed", "1994"],
        ["Height", "401 metres"]],
       ["The Varn Spire is a telecommunications and observation tower in [[lumen-harbor|Lumen Harbor]], completed "
        "in 1994. Its height is 401 metres, and its observation deck is open to visitors every day."]),
    _a("oskel-tower", "Oskel Tower",
       [["Type", "Skyscraper"], ["Location", "[[karst-city|Karst City]]"], ["Completed", "2008"],
        ["Roof height", "1,270 feet"]],
       ["The Oskel Tower is a skyscraper in [[karst-city|Karst City]], completed in 2008. Its roof height is "
        "1,270 feet, making it the tallest building in Karst City."]),
    _a("karst-city", "Karst City",
       [["Type", "City"], ["Population", "1.1 million (2020)"]],
       ["Karst City is an inland city known for its limestone caves and the [[oskel-tower|Oskel Tower]]."]),
    _a("calder-bridge", "Calder Bridge",
       [["Type", "Suspension bridge"], ["Location", "[[lumen-harbor|Lumen Harbor]]"], ["Opened", "1902"]],
       ["The Calder Bridge is a suspension bridge in [[lumen-harbor|Lumen Harbor]] that opened in 1902. It is named "
        "after [[ines-calder|Ines Calder]]."]),
    _a("lantern-festival", "Lantern Festival",
       [["Location", "[[lumen-harbor|Lumen Harbor]]"], ["First held", "1823"]],
       ["The Lantern Festival is held every autumn in [[lumen-harbor|Lumen Harbor]]. It was first held in 1823."]),
]

# Training-only cluster (used by bench/fixtures/train_tasks.py, never by LH-v1 eval cases). It shares no
# entities with the eval quiz chains (Lumen Harbor -> Ines Calder; Varn Spire vs Oskel Tower).
ARTICLES += [
    _a("mirrow-lake", "Mirrow Lake",
       [["Type", "Glacial lake"], ["Region", "[[brask-islands|Brask Islands]]"],
        ["Discovered by", "[[teodor-vale|Teodor Vale]]"], ["Area", "41 square kilometres"]],
       ["Mirrow Lake is a glacial lake on the largest of the [[brask-islands|Brask Islands]]. It was first "
        "described by the explorer [[teodor-vale|Teodor Vale]] in 1716.",
        "The lake is overlooked by the [[halden-observatory|Halden Observatory]]."]),
    _a("teodor-vale", "Teodor Vale",
       [["Born", "3 May 1688, Oster Bay"], ["Died", "1749"], ["Occupation", "Explorer, botanist"],
        ["Known for", "Discovering [[mirrow-lake|Mirrow Lake]]"]],
       ["Teodor Vale was an explorer and botanist born in Oster Bay in 1688. His survey of the "
        "[[brask-islands|Brask Islands]] described [[mirrow-lake|Mirrow Lake]] for the first time."]),
    _a("brask-islands", "Brask Islands",
       [["Type", "Island chain"], ["Islands", "9"], ["Largest town", "Helmstad"]],
       ["The Brask Islands are a chain of nine islands. The largest town is Helmstad. Landmarks include "
        "[[mirrow-lake|Mirrow Lake]], the [[halden-observatory|Halden Observatory]] and the "
        "[[brask-lighthouse|Brask Lighthouse]]."]),
    _a("halden-observatory", "Halden Observatory",
       [["Type", "Observatory"], ["Location", "[[brask-islands|Brask Islands]]"], ["Built", "1754"],
        ["Dome height", "62 feet"]],
       ["The Halden Observatory was built in 1754 above [[mirrow-lake|Mirrow Lake]]. Its dome rises 62 feet."]),
    _a("brask-lighthouse", "Brask Lighthouse",
       [["Type", "Lighthouse"], ["Location", "[[brask-islands|Brask Islands]]"], ["Built", "1761"],
        ["Height", "24 metres"]],
       ["The Brask Lighthouse was first lit in 1761. Its tower is 24 metres tall."]),
]

FEATURED_ARTICLES = ["selwyn-isles", "karst-city", "lantern-festival"]

QUIZZES = [
    {"id": "q1", "question": "In what year was the founder of Lumen Harbor born?"},
    {"id": "q2", "question": "Which is taller: the Varn Spire or the Oskel Tower?"},
    # training-only quizzes
    {"id": "t1", "question": "Who discovered Mirrow Lake?"},
    {"id": "t2", "question": "In what year was the discoverer of Mirrow Lake born?"},
    {"id": "t3", "question": "Which is older: the Halden Observatory or the Brask Lighthouse?"},
    {"id": "t4", "question": "How many islands are in the Brask Islands?"},
    {"id": "t5", "question": "Which is taller: the Halden Observatory dome or the Brask Lighthouse?"},
]

# Initial carts for training tasks that edit an existing cart (`/api/reset?case=..&preset=<name>`).
CART_PRESETS = {
    "a": {"paper-towels": 1, "banana": 3, "milk-oat": 1},
    "b": {"beans-dark": 2, "coffee-instant": 1},
}


def _t(date, desc, category, amount):
    return {"date": date, "desc": desc, "category": category, "amount": amount}


# 40 rows, 15 per page sorted by date: Starbucks rows land on page 1 (x2), page 2 (x1), page 3 (x2).
# Starbucks total = 6.45 + 5.25 + 7.10 + 4.95 + 6.40 = 30.15. Decoys: other coffee shops and STARLIGHT CINEMAS.
TRANSACTIONS = [
    _t("2026-10-01", "PAYROLL NORTHWIND CO", "Income", "2500.00"),
    _t("2026-10-01", "RIVERSIDE APARTMENTS RENT", "Housing", "-1850.00"),
    _t("2026-10-02", "MUSELET MART #22", "Groceries", "-84.12"),
    _t("2026-10-03", "STARBUCKS #1182 SEATTLE WA", "Dining", "-6.45"),
    _t("2026-10-04", "SHELL OIL 5741", "Transport", "-41.30"),
    _t("2026-10-04", "PEET'S COFFEE #210", "Dining", "-5.75"),
    _t("2026-10-05", "HARBOR CITY POWER", "Utilities", "-92.40"),
    _t("2026-10-06", "NETFLIX.COM", "Entertainment", "-15.49"),
    _t("2026-10-06", "LUMEN TRANSIT PASS", "Transport", "-60.00"),
    _t("2026-10-07", "ROSIE'S DINER", "Dining", "-23.80"),
    _t("2026-10-08", "MUSELET MART #22", "Groceries", "-56.07"),
    _t("2026-10-09", "STARBUCKS #0457", "Dining", "-5.25"),
    _t("2026-10-09", "CITY WATER DEPT", "Utilities", "-38.15"),
    _t("2026-10-10", "BLUE BOTTLE COFFEE", "Dining", "-6.00"),
    _t("2026-10-10", "PHARMACY PLUS", "Health", "-12.99"),
    _t("2026-10-11", "STARLIGHT CINEMAS", "Entertainment", "-14.00"),
    _t("2026-10-12", "MUSELET MART #22", "Groceries", "-67.45"),
    _t("2026-10-13", "SHELL OIL 5741", "Transport", "-38.90"),
    _t("2026-10-14", "BOOKS & BEANS", "Shopping", "-18.25"),
    _t("2026-10-15", "PAYROLL NORTHWIND CO", "Income", "2500.00"),
    _t("2026-10-15", "GYM MEMBERSHIP", "Health", "-45.00"),
    _t("2026-10-16", "THAI ORCHID", "Dining", "-31.60"),
    _t("2026-10-17", "STARBUCKS #1182 SEATTLE WA", "Dining", "-7.10"),
    _t("2026-10-17", "HARDWARE DEPOT", "Shopping", "-27.48"),
    _t("2026-10-18", "MUSELET MART #22", "Groceries", "-72.30"),
    _t("2026-10-19", "SPOTIFY", "Entertainment", "-11.99"),
    _t("2026-10-19", "PEET'S COFFEE #210", "Dining", "-4.95"),
    _t("2026-10-20", "LUMEN TRANSIT RELOAD", "Transport", "-20.00"),
    _t("2026-10-21", "CORNER BAKERY", "Dining", "-8.40"),
    _t("2026-10-21", "PHONE BILL", "Utilities", "-55.00"),
    _t("2026-10-22", "MUSELET MART #22", "Groceries", "-49.88"),
    _t("2026-10-23", "STARBUCKS #2210", "Dining", "-4.95"),
    _t("2026-10-24", "SHELL OIL 5741", "Transport", "-44.12"),
    _t("2026-10-25", "ONLINE TRANSFER TO SAVINGS", "Transfer", "-500.00"),
    _t("2026-10-26", "THAI ORCHID", "Dining", "-28.75"),
    _t("2026-10-27", "MUSELET MART #22", "Groceries", "-63.21"),
    _t("2026-10-28", "ROSIE'S DINER", "Dining", "-19.50"),
    _t("2026-10-29", "STARBUCKS #0457", "Dining", "-6.40"),
    _t("2026-10-30", "INTERNET SERVICE", "Utilities", "-69.99"),
    _t("2026-10-31", "BLUE BOTTLE COFFEE", "Dining", "-5.50"),
]

BANK = {"account_name": "Everyday Checking", "account_number_masked": "•••• 4821", "balance": "3,214.66"}

FORMS = {
    "volunteer": {
        "title": "Volunteer Signup — Riverside Food Bank",
        "shirt_sizes": [["", "Choose…"], ["XS", "Extra small"], ["S", "Small"], ["M", "Medium"], ["L", "Large"],
                        ["XL", "Extra large"]],
        "shifts": [["morning", "Morning (8–12)"], ["afternoon", "Afternoon (12–4)"], ["evening", "Evening (4–8)"]],
        "days": [["mon", "Monday"], ["tue", "Tuesday"], ["wed", "Wednesday"], ["thu", "Thursday"],
                 ["fri", "Friday"], ["sat", "Saturday"], ["sun", "Sunday"]],
    },
}

SEED = {
    "products": PRODUCTS,
    "featured": FEATURED,
    "emails": EMAILS,
    "articles": ARTICLES,
    "featured_articles": FEATURED_ARTICLES,
    "quizzes": QUIZZES,
    "transactions": TRANSACTIONS,
    "bank": BANK,
    "forms": FORMS,
    "cart_presets": CART_PRESETS,
}
