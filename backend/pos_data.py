"""POS data ingestion layer.

Reads the simulated POS export (CSV) once, validates and normalises it, and
exposes it in memory for backend services. This is the new read-only source of
truth: the merchant's POS owns the data; DukaanPulse only consumes it.

No database, no ORM - CSV + JSON are sufficient for this demonstration.
"""
import csv
import json
import os

import validate_pos_data

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data", "demo_pos_export")

FILES = {
    "suppliers": "suppliers.csv",
    "products": "products.csv",
    "sales": "sales.csv",
    "purchase_receipts": "purchase_receipts.csv",
    "purchase_orders": "purchase_orders.csv",
    "stock_adjustments": "stock_adjustments.csv",
    "inventory_snapshot": "inventory_snapshot.csv",
    "weather": "weather.csv",
}

FLOAT_FIELDS = {
    "products": ("cost_price", "selling_price"),
    "sales": ("unit_price", "discount", "total_amount"),
    "purchase_receipts": ("unit_cost",),
    "weather": ("temp_c", "rain_mm"),
}
INT_FIELDS = {
    "products": ("opening_stock",),
    "sales": ("quantity",),
    "purchase_receipts": ("received_quantity",),
    "purchase_orders": ("ordered_quantity", "received_quantity", "remaining_quantity"),
    "stock_adjustments": ("quantity",),
    "inventory_snapshot": ("current_stock",),
    "suppliers": ("standard_lead_time_days", "minimum_order_quantity", "minimum_order_value"),
}

_cache = {"data": None}


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _coerce(table, rows):
    for r in rows:
        for k in FLOAT_FIELDS.get(table, ()):
            if k in r and r[k] != "":
                r[k] = float(r[k])
        for k in INT_FIELDS.get(table, ()):
            if k in r and r[k] != "":
                r[k] = int(float(r[k]))
    return rows


def _read_manifest():
    with open(os.path.join(DATA_DIR, "manifest.json"), encoding="utf-8") as f:
        return json.load(f)


def load(force=False):
    """Load and normalise the POS dataset (cached)."""
    if _cache["data"] is not None and not force:
        return _cache["data"]

    missing = [f for f in FILES.values()
               if not os.path.exists(os.path.join(DATA_DIR, f))]
    if missing or not os.path.exists(os.path.join(DATA_DIR, "manifest.json")):
        raise FileNotFoundError(
            f"POS export incomplete. Missing: {missing or ['manifest.json']}. "
            f"Run: python backend/generate_demo_pos.py"
        )

    data = {"source": _read_manifest()}
    for table, fname in FILES.items():
        data[table] = _coerce(table, _read_csv(os.path.join(DATA_DIR, fname)))

    # date-part helper for range filtering
    for s in data["sales"]:
        s["sold_date"] = s["sold_at"][:10]

    data["indexes"] = {
        "product_by_id": {p["product_id"]: p for p in data["products"]},
        "supplier_by_id": {s["supplier_id"]: s for s in data["suppliers"]},
        "snapshot_by_product": {s["product_id"]: s for s in data["inventory_snapshot"]},
    }
    _cache["data"] = data
    return data


def reload():
    return load(force=True)


def dataset():
    """Public accessor used by API layer."""
    return load()


def source_info():
    """Data-source metadata + validation status for /api/demo-pos/status."""
    data = load()
    report = validate_pos_data.validate()
    manifest = data["source"]
    dates = [s["sold_date"] for s in data["sales"]] or [None]
    return {
        "source": manifest.get("source"),
        "vendor": manifest.get("vendor"),
        "note": manifest.get("note"),
        "currency": manifest.get("currency"),
        "generated_at": manifest.get("generated_at"),
        "random_seed": manifest.get("random_seed"),
        "period": manifest.get("period"),
        "data_range": {"start": min(d for d in dates if d), "end": max(d for d in dates if d)},
        "counts": report["stats"],
        "validation_ok": report["ok"],
        "validation_errors": report["errors"],
        "files": manifest.get("files", {}),
    }


# ---------------------------------------------------------------------------
# Filtering helpers (used by endpoints)
# ---------------------------------------------------------------------------
def filter_sales(start=None, end=None, product_id=None, limit=None):
    rows = dataset()["sales"]
    out = []
    for s in rows:
        if product_id and s["product_id"] != product_id:
            continue
        if start and s["sold_date"] < start:
            continue
        if end and s["sold_date"] > end:
            continue
        out.append(s)
    out.sort(key=lambda s: s["sold_at"])
    if limit:
        out = out[-limit:]
    return out


def filter_orders(status=None, supplier_id=None, product_id=None):
    rows = dataset()["purchase_orders"]
    out = []
    for o in rows:
        if status and o["status"] != status:
            continue
        if supplier_id and o["supplier_id"] != supplier_id:
            continue
        if product_id and o["product_id"] != product_id:
            continue
        out.append(o)
    return out


def product_ids(ids=None):
    rows = dataset()["products"]
    if ids:
        wanted = set(ids)
        return [p for p in rows if p["product_id"] in wanted]
    return rows
