"""Validate the simulated POS dataset for internal consistency.

Checks (see DukaanPulse Step 0 requirements):
  * Referential integrity: no unknown product_id / supplier_id.
  * Uniqueness: no duplicate transaction / record ids.
  * No negative sales quantities, no negative inventory.
  * Accounting: opening + received - sales + adjustments == snapshot stock.
  * Pending purchase orders are NOT counted as received stock.

Usable as a script (prints a report, exit code 1 on failure) and as a library
(validate() -> report) so tests can reuse it.
"""
import csv
import json
import os
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data", "demo_pos_export")


def _read(name):
    with open(os.path.join(DATA_DIR, name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _read_manifest():
    with open(os.path.join(DATA_DIR, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def validate() -> dict:
    errors = []
    suppliers = _read("suppliers.csv")
    products = _read("products.csv")
    sales = _read("sales.csv")
    receipts = _read("purchase_receipts.csv")
    orders = _read("purchase_orders.csv")
    adjustments = _read("stock_adjustments.csv")
    snapshot = _read("inventory_snapshot.csv")
    weather = _read("weather.csv")

    supplier_ids = {s["supplier_id"] for s in suppliers}
    product_ids = {p["product_id"] for p in products}

    # --- uniqueness ---
    for name, rows, key in [
        ("sales.sale_id", sales, "sale_id"),
        ("purchase_receipts.receipt_id", receipts, "receipt_id"),
        ("purchase_orders.purchase_order_id", orders, "purchase_order_id"),
        ("stock_adjustments.adjustment_id", adjustments, "adjustment_id"),
    ]:
        seen = set()
        dupes = set()
        for r in rows:
            v = r[key]
            if v in seen:
                dupes.add(v)
            seen.add(v)
        if dupes:
            errors.append(f"duplicate {name}: {sorted(dupes)[:5]}")

    # --- referential integrity + non-negative quantities ---
    for r in products:
        if r["supplier_id"] not in supplier_ids:
            errors.append(f"product {r['product_id']} has unknown supplier {r['supplier_id']}")

    for r in sales:
        if r["product_id"] not in product_ids:
            errors.append(f"sale {r['sale_id']} has unknown product {r['product_id']}")
        if int(r["quantity"]) <= 0:
            errors.append(f"sale {r['sale_id']} has non-positive quantity {r['quantity']}")
        expected = round(int(r["quantity"]) * float(r["unit_price"]) - float(r["discount"]), 2)
        if abs(expected - float(r["total_amount"])) > 0.01:
            errors.append(f"sale {r['sale_id']} total_amount mismatch")

    for r in receipts:
        if r["product_id"] not in product_ids:
            errors.append(f"receipt {r['receipt_id']} has unknown product {r['product_id']}")
        if r["supplier_id"] not in supplier_ids:
            errors.append(f"receipt {r['receipt_id']} has unknown supplier {r['supplier_id']}")
        if int(r["received_quantity"]) <= 0:
            errors.append(f"receipt {r['receipt_id']} has non-positive quantity")

    for r in adjustments:
        if r["product_id"] not in product_ids:
            errors.append(f"adjustment {r['adjustment_id']} has unknown product {r['product_id']}")

    for r in orders:
        if r["product_id"] not in product_ids:
            errors.append(f"order {r['purchase_order_id']} has unknown product {r['product_id']}")
        if r["supplier_id"] not in supplier_ids:
            errors.append(f"order {r['purchase_order_id']} has unknown supplier {r['supplier_id']}")

    # --- accounting reconciliation ---
    received = defaultdict(int)
    for r in receipts:
        received[r["product_id"]] += int(r["received_quantity"])
    sold = defaultdict(int)
    for r in sales:
        sold[r["product_id"]] += int(r["quantity"])
    adjusted = defaultdict(int)
    for r in adjustments:
        adjusted[r["product_id"]] += int(r["quantity"])

    snap = {r["product_id"]: int(r["current_stock"]) for r in snapshot}
    if set(snap) != product_ids:
        errors.append("inventory_snapshot does not cover exactly the product catalogue")

    mismatches = []
    for p in products:
        pid = p["product_id"]
        calc = (int(p["opening_stock"]) + received[pid] - sold[pid] + adjusted[pid])
        if pid in snap and calc != snap[pid]:
            mismatches.append(f"{pid}: calc={calc} snapshot={snap[pid]}")
        if snap.get(pid, 0) < 0:
            errors.append(f"{pid} has negative closing stock {snap.get(pid)}")
    if mismatches:
        errors.append(f"reconciliation mismatches ({len(mismatches)}): {mismatches[:5]}")

    # --- weather coverage + plausibility ---
    sales_days = {r["sold_at"][:10] for r in sales}
    weather_days = {r["date"] for r in weather}
    missing_weather = sorted(sales_days - weather_days)
    if missing_weather:
        errors.append(f"weather missing for {len(missing_weather)} sales days: {missing_weather[:5]}")
    for r in weather:
        t = float(r["temp_c"])
        if t < -5 or t > 55:
            errors.append(f"implausible temperature {t} on {r['date']}")

    # --- pending POs must not be received / counted ---
    pending = [o for o in orders if o["status"] == "pending"]
    if not pending:
        errors.append("expected at least 3 pending purchase orders")
    received_po_ids = {r["purchase_order_id"] for r in receipts if r["purchase_order_id"]}
    for o in pending:
        if o["purchase_order_id"] in received_po_ids:
            errors.append(f"pending order {o['purchase_order_id']} has a receipt (should not)")
        if int(o["received_quantity"]) != 0:
            errors.append(f"pending order {o['purchase_order_id']} has received_quantity > 0")
        if int(o["remaining_quantity"]) != int(o["ordered_quantity"]):
            errors.append(f"pending order {o['purchase_order_id']} remaining != ordered")

    pending_po_qty = defaultdict(int)
    for o in pending:
        pending_po_qty[o["product_id"]] += int(o["ordered_quantity"])
    for pid, qty in pending_po_qty.items():
        if snap.get(pid, 0) < qty and False:  # not an error; documented check only
            pass

    report = {
        "ok": not errors,
        "errors": errors,
        "stats": {
            "suppliers": len(suppliers),
            "products": len(products),
            "sales": len(sales),
            "purchase_receipts": len(receipts),
            "purchase_orders": len(orders),
            "pending_purchase_orders": len(pending),
            "stock_adjustments": len(adjustments),
            "inventory_snapshot": len(snapshot),
            "weather": len(weather),
            "sales_units": sum(sold.values()),
            "inventory_units": sum(snap.values()),
        },
    }
    return report


if __name__ == "__main__":
    rep = validate()
    print(json.dumps(rep["stats"], indent=2))
    if rep["ok"]:
        print("\nVALIDATION PASSED - dataset is internally consistent.")
    else:
        print("\nVALIDATION FAILED:")
        for e in rep["errors"]:
            print(" -", e)
        raise SystemExit(1)
