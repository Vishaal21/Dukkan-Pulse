"""Generate a simulated POS export for DukaanPulse (demo data only).

This produces CSV files that mimic the export of a retail POS system, so the
analytics layer can consume them. It is NOT data from Paytm, Zoho or any real
POS vendor - it is fully simulated demo data.

Data integrity is guaranteed by construction: a day-by-day inventory
simulation produces sales, receipts and adjustments such that

    opening_stock + received_purchases - sales + adjustments = closing_stock

and the closing stock is written to inventory_snapshot.csv. Pending purchase
orders are scheduled to arrive after the simulated period and are NOT counted
as current stock.

Output (backend/data/demo_pos_export/):
    products.csv, sales.csv, purchase_receipts.csv, suppliers.csv,
    purchase_orders.csv, stock_adjustments.csv, inventory_snapshot.csv,
    weather.csv, manifest.json

Deterministic: fixed random seed -> identical output every run.
Run:  backend/.venv/bin/python backend/generate_demo_pos.py
"""
import csv
import json
import os
import random
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "data", "demo_pos_export")

SEED = 20261114
END_DATE = date(2026, 11, 14)          # last day with recorded activity ("today")
DAYS = 365                              # one full year, so seasonality is visible
START_DATE = END_DATE - timedelta(days=DAYS - 1)
GENERATED_AT = "2026-11-14T23:59:00"   # fixed for reproducible output (end of today)
CURRENCY = "INR"

# ---------------------------------------------------------------------------
# Suppliers: id, name, lead_time_days, min_order_quantity, min_order_value
# ---------------------------------------------------------------------------
SUPPLIERS = [
    ("SUP-01", "Sharma Distributors", 2, 20, 2000),
    ("SUP-02", "Gupta Traders", 3, 24, 1500),
    ("SUP-03", "Mehta Wholesale Mart", 5, 50, 5000),
    ("SUP-04", "Patel FMCG Supply", 4, 30, 3000),
    ("SUP-05", "Singh Beverages & Snacks", 1, 12, 1000),
]
SUPPLIER_LEAD = {s[0]: s[2] for s in SUPPLIERS}
SUPPLIER_MOQ = {s[0]: s[3] for s in SUPPLIERS}

# ---------------------------------------------------------------------------
# Products: name, category, unit, pack_size, cost_price, selling_price
# ---------------------------------------------------------------------------
_CATALOG = [
    ("Maggi Noodles 70g", "Noodles", "packet", "70g", 12, 14),
    ("Maggi Noodles 140g", "Noodles", "packet", "140g", 22, 26),
    ("Top Ramen 70g", "Noodles", "packet", "70g", 11, 13),
    ("Yippee Noodles 60g", "Noodles", "packet", "60g", 10, 12),
    ("Parle-G Biscuit 250g", "Biscuits", "packet", "250g", 20, 25),
    ("Parle-G Biscuit 100g", "Biscuits", "packet", "100g", 9, 10),
    ("Britannia Good Day 200g", "Biscuits", "packet", "200g", 30, 40),
    ("Britannia Marie 250g", "Biscuits", "packet", "250g", 26, 32),
    ("Oreo Biscuit 120g", "Biscuits", "packet", "120g", 25, 30),
    ("Britannia NutriChoice 300g", "Biscuits", "packet", "300g", 35, 45),
    ("Amul Butter 100g", "Dairy", "pack", "100g", 52, 58),
    ("Amul Butter 500g", "Dairy", "pack", "500g", 245, 265),
    ("Amul Milk 500ml", "Dairy", "pouch", "500ml", 25, 28),
    ("Amul Cheese 200g", "Dairy", "pack", "200g", 110, 125),
    ("Mother Dairy Curd 400g", "Dairy", "cup", "400g", 35, 42),
    ("Tata Salt 1kg", "Grocery", "packet", "1kg", 22, 28),
    ("Tata Tea Gold 250g", "Beverages", "packet", "250g", 130, 150),
    ("Red Label Tea 250g", "Beverages", "packet", "250g", 100, 115),
    ("Nescafe Classic 50g", "Beverages", "jar", "50g", 150, 175),
    ("Bournvita 500g", "Beverages", "jar", "500g", 210, 235),
    ("Coca Cola 750ml", "Beverages", "bottle", "750ml", 32, 40),
    ("Thums Up 750ml", "Beverages", "bottle", "750ml", 32, 40),
    ("Bisleri Water 1L", "Beverages", "bottle", "1L", 12, 20),
    ("Real Juice 1L", "Beverages", "carton", "1L", 95, 110),
    ("Rasna Powder 500g", "Beverages", "pack", "500g", 90, 105),
    ("Lays Classic 52g", "Snacks", "packet", "52g", 15, 20),
    ("Kurkure 90g", "Snacks", "packet", "90g", 16, 20),
    ("Haldiram Bhujia 200g", "Snacks", "packet", "200g", 45, 55),
    ("Bingo Mad Angles 66g", "Snacks", "packet", "66g", 15, 20),
    ("Aashirvaad Atta 5kg", "Grocery", "bag", "5kg", 210, 240),
    ("Fortune Sunflower Oil 1L", "Grocery", "bottle", "1L", 120, 135),
    ("Saffola Cooking Oil 1L", "Grocery", "bottle", "1L", 140, 160),
    ("Toor Dal 1kg", "Grocery", "packet", "1kg", 130, 150),
    ("Basmati Rice 1kg", "Grocery", "packet", "1kg", 110, 130),
    ("Sugar 1kg", "Grocery", "packet", "1kg", 42, 50),
    ("Colgate Toothpaste 100g", "Personal Care", "tube", "100g", 45, 55),
    ("Colgate Toothpaste 200g", "Personal Care", "tube", "200g", 82, 95),
    ("Dove Soap 100g", "Personal Care", "bar", "100g", 42, 52),
    ("Lifebuoy Soap 100g", "Personal Care", "bar", "100g", 28, 35),
    ("Clinic Plus Shampoo 180ml", "Personal Care", "bottle", "180ml", 95, 110),
    ("Surf Excel 1kg", "Household", "packet", "1kg", 105, 120),
    ("Vim Dishwash Bar 200g", "Household", "bar", "200g", 18, 22),
    ("Harpic 500ml", "Household", "bottle", "500ml", 85, 99),
    ("Dairy Milk 40g", "Confectionery", "bar", "40g", 20, 25),
    ("KitKat 27g", "Confectionery", "bar", "27g", 18, 22),
    ("Everest Turmeric 100g", "Spices", "packet", "100g", 25, 32),
    ("MDH Chilli Powder 100g", "Spices", "packet", "100g", 38, 48),
    ("Fleece Blanket Single", "Seasonal", "piece", "single", 250, 350),
    ("Room Heater 2000W", "Seasonal", "piece", "1 piece", 900, 1200),
    ("Sugarcane 1kg", "Fruits", "kg", "1kg", 25, 35),
    ("Banana (dozen)", "Fruits", "dozen", "12 pc", 40, 60),
    ("Coconut (whole)", "Fruits", "piece", "1 piece", 35, 50),
    ("Thekua 500g", "Sweets", "pack", "500g", 90, 120),
]

SKU_PREFIX = {
    "Noodles": "NDL", "Biscuits": "BSC", "Dairy": "DRY", "Beverages": "BEV",
    "Snacks": "SNK", "Grocery": "GRO", "Personal Care": "PC", "Household": "HHD",
    "Confectionery": "CNF", "Spices": "SPC", "Seasonal": "SEA", "Fruits": "FRT",
    "Sweets": "SWT",
}

# ---------------------------------------------------------------------------
# Weather (simulated, Delhi-like) + seasonality + festivals.
# All deterministic: a fixed weather series drives temperature-linked demand.
# ---------------------------------------------------------------------------
MONTH_MEAN_TEMP = {1: 14, 2: 18, 3: 24, 4: 30, 5: 34, 6: 34,
                   7: 32, 8: 31, 9: 29, 10: 26, 11: 20, 12: 15}
MONSOON_MONTHS = {6, 7, 8, 9}

# General retail month index: festive Oct-Nov spike, monsoon lull.
MONTH_INDEX = {1: 1.05, 2: 0.98, 3: 1.05, 4: 1.00, 5: 1.02, 6: 0.95,
               7: 0.95, 8: 1.05, 9: 1.00, 10: 1.15, 11: 1.20, 12: 1.12}

# Festival windows (date, name) with per-category boosts, applied a few days around.
FESTIVALS = [
    (date(2025, 12, 25), "Christmas",      {"Confectionery": 1.8, "Snacks": 1.5, "Beverages": 1.3}),
    (date(2026, 1, 1),   "New Year",       {"Snacks": 1.4, "Beverages": 1.4, "Confectionery": 1.4}),
    (date(2026, 1, 26),  "Republic Day",   {"Snacks": 1.3, "Beverages": 1.2}),
    (date(2026, 3, 3),   "Holi",           {"Snacks": 1.6, "Beverages": 1.5, "Confectionery": 1.3}),
    (date(2026, 3, 20),  "Eid",            {"Snacks": 1.5, "Dairy": 1.3, "Confectionery": 1.4}),
    (date(2026, 8, 15),  "Independence Day", {"Snacks": 1.3, "Beverages": 1.2, "Confectionery": 1.3}),
    (date(2026, 8, 28),  "Raksha Bandhan", {"Confectionery": 1.5, "Snacks": 1.4, "Dairy": 1.2}),
    (date(2026, 9, 14),  "Ganesh Chaturthi", {"Confectionery": 1.5, "Snacks": 1.3, "Dairy": 1.2}),
    (date(2026, 10, 20), "Dussehra",       {"Confectionery": 1.7, "Snacks": 1.5, "Biscuits": 1.3, "Beverages": 1.2}),
    (date(2026, 11, 8),  "Diwali",         {"Confectionery": 1.9, "Snacks": 1.6, "Biscuits": 1.4, "Beverages": 1.3, "Dairy": 1.2}),
    (date(2026, 11, 16), "Chhath Puja",    {"Thekua": 1.8, "Sugarcane": 1.7, "Coconut": 1.6,
                                             "Banana": 1.5, "Amul Milk": 1.3, "Curd": 1.3}),
]
FESTIVAL_LEAD = 5   # days before the festival date
FESTIVAL_TAIL = 1   # days after

# Products we deliberately leave low on stock near the end of the period, so the
# demo shows festival and temperature driven "order now" reasons. Recorded as a
# normal stock adjustment, so the accounting still reconciles.
SHOWCASE_LOW = {"Nescafe Classic 50g", "Dairy Milk 40g", "Room Heater 2000W", "Sugarcane 1kg", "Thekua 500g"}
# A product we deliberately keep well covered, so the urgent list reads cleanly
# (no urgent row whose only reason is pack-size rounding).
SHOWCASE_HIGH = {"Colgate Toothpaste 200g"}

# Temperature-sensitive products (matched by name).
COLD_DRINK_KEYS = ("Coca Cola", "Thums Up", "Bisleri", "Real Juice", "Rasna")
HOT_DRINK_KEYS = ("Tata Tea", "Red Label Tea", "Nescafe")
COLD_WEATHER_KEYS = ("Blanket", "Heater")   # sold more when it is cold


def _build_weather():
    """Deterministic daily temperature/rain series for the whole period."""
    rng = random.Random(SEED + 7)
    rows = []
    for day in range(DAYS):
        d = START_DATE + timedelta(days=day)
        temp = round(MONTH_MEAN_TEMP[d.month] + rng.gauss(0, 2.5), 1)
        if d.month in MONSOON_MONTHS and rng.random() < 0.55:
            rain = round(rng.uniform(1, 35), 1)
        elif rng.random() < 0.08:
            rain = round(rng.uniform(0.5, 8), 1)
        else:
            rain = 0.0
        rows.append({"date": d.isoformat(), "temp_c": temp, "rain_mm": rain})
    return rows


def _temp_factor(name, temp):
    """How much temperature changes demand for a product."""
    if any(k in name for k in COLD_DRINK_KEYS):
        return max(0.6, 1 + (temp - 28) * 0.03)     # hot -> more cold drinks
    if any(k in name for k in HOT_DRINK_KEYS):
        return max(0.7, 1 + (25 - temp) * 0.02)      # cold -> more tea/coffee
    if any(k in name for k in COLD_WEATHER_KEYS):
        return max(0.7, 1 + (25 - temp) * 0.05)      # cold -> more blankets/heaters
    return 1.0


def festival_multiplier(product, boosts):
    """Festival demand boost for one product.

    Keys in `boosts` may be a product category (e.g. "Snacks") or a product-name
    keyword (e.g. "Thekua", "Sugarcane"). This lets a festival target believable
    items (Chhath -> thekua/fruits/milk) instead of a whole category.
    """
    name = product["name"].lower()
    best = 1.0
    for key, value in boosts.items():
        if key == product["category"] or key.lower() in name:
            best = max(best, value)
    return best


def _festival_factor(product, d):
    f = 1.0
    for fdate, _name, boosts in FESTIVALS:
        if fdate - timedelta(days=FESTIVAL_LEAD) <= d <= fdate + timedelta(days=FESTIVAL_TAIL):
            f *= festival_multiplier(product, boosts)
    return f


def _build_products():
    products = []
    for i, (name, cat, unit, pack, cost, sell) in enumerate(_CATALOG, start=1):
        pid = f"P{i:03d}"
        sku = f"{SKU_PREFIX.get(cat, 'GEN')}-{i:03d}"
        supplier = SUPPLIERS[i % len(SUPPLIERS)][0]
        products.append({
            "product_id": pid, "sku": sku, "name": name, "category": cat,
            "unit": unit, "pack_size": pack, "cost_price": float(cost),
            "selling_price": float(sell), "supplier_id": supplier,
        })
    return products


def _money(x):
    return f"{round(float(x) + 0.0, 2):.2f}"


def _ts(d: date, rng: random.Random) -> str:
    return datetime(d.year, d.month, d.day,
                    rng.randint(8, 21), rng.randint(0, 59),
                    rng.randint(0, 59)).isoformat(timespec="seconds")


def generate():
    rng = random.Random(SEED)
    products = _build_products()

    # Demand profiles: fast / medium / slow (guaranteed mix).
    idx = list(range(len(products)))
    rng.shuffle(idx)
    fast = set(idx[:9])
    slow = set(idx[9:16])  # ~7 slow movers
    base_demand = {}
    for i in idx:
        if i in fast:
            base_demand[i] = round(rng.uniform(8, 14), 1)
        elif i in slow:
            base_demand[i] = round(rng.uniform(0.3, 1.1), 1)
        else:
            base_demand[i] = round(rng.uniform(3, 7), 1)

    # Opening stock: enough cover, but a few deliberately lean.
    for i, p in enumerate(products):
        base = base_demand[i]
        cover_days = rng.randint(10, 20) if i in fast else rng.randint(18, 32)
        p["opening_stock"] = max(4, int(round(base * cover_days)) + rng.randint(0, 6))
        p["_base"] = base

    sales_rows, receipts_rows, po_rows, adj_rows = [], [], [], []

    weather_rows = _build_weather()
    temp_by_date = {w["date"]: w["temp_c"] for w in weather_rows}

    sale_seq = 0
    receipt_seq = 0
    po_seq = 0
    adj_seq = 0

    for i, p in enumerate(products):
        pid = p["product_id"]
        base = p["_base"]
        lead = SUPPLIER_LEAD[p["supplier_id"]]
        moq = SUPPLIER_MOQ[p["supplier_id"]]
        reorder_point = int(round(base * (lead + 3))) + 2
        reorder_qty = max(moq, int(round(base * (lead + 28))))

        stock = p["opening_stock"]
        arrivals = {}       # day -> list[(po_id, qty)]
        open_orders = []     # po_ids outstanding
        po_by_id = {}

        for day in range(1, DAYS + 1):
            d = START_DATE + timedelta(days=day - 1)

            # 1. receive arrivals scheduled today
            for po_id, qty in arrivals.pop(day, []):
                stock += qty
                receipt_seq += 1
                receipts_rows.append({
                    "receipt_id": f"R{receipt_seq:05d}",
                    "purchase_order_id": po_id,
                    "supplier_id": p["supplier_id"],
                    "product_id": pid,
                    "received_at": _ts(d, rng),
                    "received_quantity": qty,
                    "unit_cost": _money(p["cost_price"]),
                })
                po = po_by_id[po_id]
                po["received_quantity"] = qty
                po["remaining_quantity"] = po["ordered_quantity"] - qty
                po["status"] = "received" if po["remaining_quantity"] <= 0 else "partially_received"
                if po_id in open_orders:
                    open_orders.remove(po_id)

            # 2. record sales, capped to available stock
            #    demand responds to the month, festivals, and temperature
            temp = temp_by_date[d.isoformat()]
            seasonal = (MONTH_INDEX[d.month]
                        * _festival_factor(p, d)
                        * _temp_factor(p["name"], temp))
            expected = base * seasonal
            demand = max(0, int(round(rng.gauss(expected, expected * 0.4))))
            sold = min(demand, stock)
            if sold > 0:
                stock -= sold
                sales_rows.append((d, pid, sold, p["selling_price"], rng))

            # 3. reorder if low and nothing outstanding
            if stock <= reorder_point and not open_orders:
                po_seq += 1
                po_id = f"PO{po_seq:05d}"
                arrival_day = day + lead
                po = {
                    "purchase_order_id": po_id,
                    "supplier_id": p["supplier_id"],
                    "product_id": pid,
                    "ordered_quantity": reorder_qty,
                    "received_quantity": 0,
                    "remaining_quantity": reorder_qty,
                    "order_date": d.isoformat(),
                    "expected_delivery_date": (START_DATE + timedelta(days=arrival_day - 1)).isoformat(),
                    "status": "pending",
                }
                po_rows.append(po)
                po_by_id[po_id] = po
                open_orders.append(po_id)
                arrivals.setdefault(arrival_day, []).append((po_id, reorder_qty))

        # 4. occasional stock adjustments (damaged / expired / returned)
        if i % 7 == 0 and stock > 2:
            adj_seq += 1
            adj_day = START_DATE + timedelta(days=rng.randint(10, DAYS - 1))
            loss = min(stock, rng.randint(1, 3))
            stock -= loss
            adj_rows.append({
                "adjustment_id": f"A{adj_seq:04d}", "product_id": pid,
                "quantity": -loss, "reason": rng.choice(["damaged", "expired"]),
                "adjusted_at": _ts(adj_day, rng),
            })
        if i % 11 == 0 and stock > 0:
            adj_seq += 1
            adj_day = START_DATE + timedelta(days=rng.randint(10, DAYS - 1))
            add = rng.randint(1, 2)
            stock += add
            adj_rows.append({
                "adjustment_id": f"A{adj_seq:04d}", "product_id": pid,
                "quantity": add, "reason": "returned",
                "adjusted_at": _ts(adj_day, rng),
            })

        # showcase products: leave them low near the end (recorded as a loss),
        # so urgent recommendations show festival / temperature reasons.
        if p["name"] in SHOWCASE_LOW:
            target = max(2, int(round(base * lead * 0.5)))
            if stock > target:
                adj_seq += 1
                loss = stock - target
                stock = target
                fixed_day = (START_DATE + timedelta(days=DAYS - 3)).isoformat()
                adj_rows.append({
                    "adjustment_id": f"A{adj_seq:04d}", "product_id": pid,
                    "quantity": -loss, "reason": "damaged",
                    "adjusted_at": fixed_day + "T12:00:00",
                })

        if p["name"] in SHOWCASE_HIGH:
            target = int(round(base * (lead + 25)))
            if stock < target:
                adj_seq += 1
                gain = target - stock
                stock = target
                fixed_day = (START_DATE + timedelta(days=DAYS - 3)).isoformat()
                adj_rows.append({
                    "adjustment_id": f"A{adj_seq:04d}", "product_id": pid,
                    "quantity": gain, "reason": "returned",
                    "adjusted_at": fixed_day + "T12:00:00",
                })

        p["_closing"] = stock

    # ---- group item-level sales into invoices per day ----
    sales_final = []
    by_day = {}
    for (d, pid, qty, price, r) in sales_rows:
        by_day.setdefault(d, []).append((pid, qty, price, r))
    for d in sorted(by_day):
        items = by_day[d]
        rng.shuffle(items)
        k = 0
        pos = 0
        while pos < len(items):
            size = rng.randint(1, 4)
            chunk = items[pos:pos + size]
            pos += size
            k += 1
            invoice_id = f"INV-{d.strftime('%Y%m%d')}-{k:03d}"
            for (pid, qty, price, r) in chunk:
                sale_seq += 1
                discount = 0
                if r.random() < 0.15:
                    discount = round(qty * price * r.choice([0.05, 0.1]), 2)
                total = round(qty * price - discount, 2)
                sales_final.append({
                    "sale_id": f"S{sale_seq:06d}",
                    "invoice_id": invoice_id,
                    "sold_at": _ts(d, r),
                    "product_id": pid,
                    "quantity": qty,
                    "unit_price": _money(price),
                    "discount": _money(discount),
                    "total_amount": _money(total),
                })

    # ---- ensure at least 3 pending purchase orders (open, not yet received) ----
    pending = [po for po in po_rows if po["status"] == "pending"]
    if len(pending) < 3:
        lean = sorted(products, key=lambda p: p["_closing"])[: 3 - len(pending)]
        for p in lean:
            po_seq += 1
            expected = (END_DATE + timedelta(days=rng.randint(2, 5))).isoformat()
            po_rows.append({
                "purchase_order_id": f"PO{po_seq:05d}",
                "supplier_id": p["supplier_id"],
                "product_id": p["product_id"],
                "ordered_quantity": max(SUPPLIER_MOQ[p["supplier_id"]],
                                         int(round(p["_base"] * (SUPPLIER_LEAD[p["supplier_id"]] + 28)))),
                "received_quantity": 0,
                "remaining_quantity": 0,
                "order_date": END_DATE.isoformat(),
                "expected_delivery_date": expected,
                "status": "pending",
            })
        for po in po_rows:
            if po["status"] == "pending" and po["remaining_quantity"] == 0:
                po["remaining_quantity"] = po["ordered_quantity"]

    products_out = [{k: v for k, v in p.items() if not k.startswith("_")} for p in products]
    snapshot = [{
        "product_id": p["product_id"],
        "current_stock": p["_closing"],
        "snapshot_timestamp": GENERATED_AT,
    } for p in products]

    return {
        "suppliers": [{
            "supplier_id": s[0], "supplier_name": s[1],
            "standard_lead_time_days": s[2],
            "minimum_order_quantity": s[3],
            "minimum_order_value": s[4],
        } for s in SUPPLIERS],
        "products": products_out,
        "sales": sales_final,
        "purchase_receipts": receipts_rows,
        "purchase_orders": po_rows,
        "stock_adjustments": adj_rows,
        "inventory_snapshot": snapshot,
        "weather": weather_rows,
    }


def write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow(r)


SCHEMA = {
    "suppliers.csv": ["supplier_id", "supplier_name", "standard_lead_time_days",
                      "minimum_order_quantity", "minimum_order_value"],
    "products.csv": ["product_id", "sku", "name", "category", "unit", "pack_size",
                     "cost_price", "selling_price", "supplier_id", "opening_stock"],
    "sales.csv": ["sale_id", "invoice_id", "sold_at", "product_id", "quantity",
                  "unit_price", "discount", "total_amount"],
    "purchase_receipts.csv": ["receipt_id", "purchase_order_id", "supplier_id",
                              "product_id", "received_at", "received_quantity", "unit_cost"],
    "purchase_orders.csv": ["purchase_order_id", "supplier_id", "product_id",
                            "ordered_quantity", "received_quantity", "remaining_quantity",
                            "order_date", "expected_delivery_date", "status"],
    "stock_adjustments.csv": ["adjustment_id", "product_id", "quantity", "reason", "adjusted_at"],
    "inventory_snapshot.csv": ["product_id", "current_stock", "snapshot_timestamp"],
    "weather.csv": ["date", "temp_c", "rain_mm"],
}


def main():
    data = generate()
    os.makedirs(OUT_DIR, exist_ok=True)
    for fname, cols in SCHEMA.items():
        write_csv(os.path.join(OUT_DIR, fname), data[fname.replace(".csv", "")], cols)

    manifest = {
        "source": "Simulated demo POS export (generated for DukaanPulse)",
        "vendor": None,
        "note": "Not an export from Paytm, Zoho or any real POS vendor. Fully simulated.",
        "currency": CURRENCY,
        "generated_at": GENERATED_AT,
        "random_seed": SEED,
        "period": {"start": START_DATE.isoformat(), "end": END_DATE.isoformat(), "days": DAYS},
        "record_counts": {
            "suppliers": len(data["suppliers"]),
            "products": len(data["products"]),
            "sales": len(data["sales"]),
            "purchase_receipts": len(data["purchase_receipts"]),
            "purchase_orders": len(data["purchase_orders"]),
            "stock_adjustments": len(data["stock_adjustments"]),
            "inventory_snapshot": len(data["inventory_snapshot"]),
            "weather": len(data["weather"]),
        },
        "files": {f: c for f, c in SCHEMA.items()},
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"wrote {len(SCHEMA) + 1} files to {OUT_DIR}")
    print("record_counts:", manifest["record_counts"])


if __name__ == "__main__":
    main()
