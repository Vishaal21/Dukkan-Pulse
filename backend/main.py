"""DukaanPulse backend - FastAPI entry point.

New direction: DukaanPulse is a read-only analytics layer on top of a
merchant's existing POS. For this MVP we consume a *simulated* POS export
(see backend/data/demo_pos_export). All endpoints here are read-only - the
POS owns the data; DukaanPulse never writes it.

Response shape (list endpoints):
    { "source": "simulated_demo_pos", "count": <n>, "items": [ ... ] }
"""
import os

import assistant
import pos_data
import recommendations
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="DukaanPulse API", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SOURCE = "simulated_demo_pos"


def _store():
    try:
        return pos_data.dataset()
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "dukaanpulse"}


@app.get("/api/demo-pos/status")
def demo_pos_status():
    """Import status + data-source metadata (identifies data as simulated)."""
    try:
        return pos_data.source_info()
    except FileNotFoundError as e:
        raise HTTPException(503, str(e))


@app.get("/api/pos/products")
def pos_products(
    category: str | None = None,
    supplier_id: str | None = None,
    ids: str | None = None,
):
    """Product catalogue. Filter by category, supplier, or comma-separated ids."""
    rows = _store()["products"]
    if category:
        rows = [p for p in rows if p["category"] == category]
    if supplier_id:
        rows = [p for p in rows if p["supplier_id"] == supplier_id]
    if ids:
        wanted = {x.strip() for x in ids.split(",") if x.strip()}
        rows = [p for p in rows if p["product_id"] in wanted]
    return {"source": SOURCE, "count": len(rows), "items": rows}


@app.get("/api/pos/inventory")
def pos_inventory(product_id: str | None = None):
    """Current stock = latest inventory snapshot from the POS, joined to products."""
    data = _store()
    by_id = data["indexes"]["product_by_id"]
    items = []
    for snap in data["inventory_snapshot"]:
        if product_id and snap["product_id"] != product_id:
            continue
        p = by_id.get(snap["product_id"], {})
        items.append({
            "product_id": snap["product_id"],
            "name": p.get("name"),
            "sku": p.get("sku"),
            "category": p.get("category"),
            "unit": p.get("unit"),
            "pack_size": p.get("pack_size"),
            "supplier_id": p.get("supplier_id"),
            "current_stock": snap["current_stock"],
            "snapshot_timestamp": snap["snapshot_timestamp"],
        })
    items.sort(key=lambda x: x["current_stock"])
    return {"source": SOURCE, "count": len(items), "items": items}


@app.get("/api/pos/sales")
def pos_sales(
    start: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    end: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    product_id: str | None = None,
    limit: int = Query(200, ge=1, le=20000),
):
    """Historical item-level sales, filterable by date range and product."""
    rows = pos_data.filter_sales(start=start, end=end, product_id=product_id, limit=limit)
    return {"source": SOURCE, "count": len(rows), "items": rows}


@app.get("/api/pos/purchase-receipts")
def pos_purchase_receipts(
    supplier_id: str | None = None,
    product_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
):
    """Historical received purchases (physical goods actually received)."""
    rows = _store()["purchase_receipts"]
    def keep(r):
        if supplier_id and r["supplier_id"] != supplier_id:
            return False
        if product_id and r["product_id"] != product_id:
            return False
        day = r["received_at"][:10]
        if start and day < start:
            return False
        if end and day > end:
            return False
        return True
    rows = [r for r in rows if keep(r)]
    return {"source": SOURCE, "count": len(rows), "items": rows}


@app.get("/api/pos/suppliers")
def pos_suppliers():
    """Supplier directory with lead times and order constraints."""
    rows = _store()["suppliers"]
    return {"source": SOURCE, "count": len(rows), "items": rows}


@app.get("/api/pos/purchase-orders")
def pos_purchase_orders(
    status: str | None = None,
    supplier_id: str | None = None,
    product_id: str | None = None,
):
    """Purchase orders (pending + historical). Pending orders are NOT stock."""
    rows = pos_data.filter_orders(status=status, supplier_id=supplier_id, product_id=product_id)
    return {"source": SOURCE, "count": len(rows), "items": rows}


@app.get("/api/pos/stock-adjustments")
def pos_stock_adjustments(product_id: str | None = None):
    """Manual stock corrections recorded by the POS (damaged/expired/returned)."""
    rows = _store()["stock_adjustments"]
    if product_id:
        rows = [r for r in rows if r["product_id"] == product_id]
    return {"source": SOURCE, "count": len(rows), "items": rows}


@app.get("/api/pos/weather")
def pos_weather(
    start: str | None = Query(None, description="YYYY-MM-DD inclusive"),
    end: str | None = Query(None, description="YYYY-MM-DD inclusive"),
):
    """Simulated daily weather (temperature/rain) aligned to the sales period."""
    rows = _store()["weather"]

    def keep(r):
        if start and r["date"] < start:
            return False
        if end and r["date"] > end:
            return False
        return True

    rows = [r for r in rows if keep(r)]
    return {"source": SOURCE, "count": len(rows), "items": rows}


# ---------------------------------------------------------------------------
# Smart Recommendation Engine (deterministic; read-only)
# ---------------------------------------------------------------------------
@app.get("/api/recommendations")
def get_recommendations(
    window_days: int = Query(recommendations.ANALYSIS_WINDOW_DAYS, ge=1, le=365),
    cover_days: int = Query(recommendations.TARGET_COVER_DAYS, ge=0, le=180),
):
    """Per-product metrics + reorder list + slow movers + summary."""
    return recommendations.overview(window_days=window_days, cover_days=cover_days)


@app.get("/api/recommendations/budget")
def get_budget_plan(
    budget: float = Query(..., gt=0, description="Purchase budget in INR"),
    window_days: int = Query(recommendations.ANALYSIS_WINDOW_DAYS, ge=1, le=365),
    cover_days: int = Query(recommendations.TARGET_COVER_DAYS, ge=0, le=180),
):
    """Prioritised purchase plan for a given budget."""
    try:
        return recommendations.budget_plan(budget, window_days=window_days, cover_days=cover_days)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/recommendations/reason")
def recommendation_reason(product_id: str = Query(..., description="Product id")):
    """Detailed plain-English reason for one recommendation. Uses the LLM if
    configured, otherwise a deterministic explanation. Read only."""
    try:
        return assistant.detailed_reason(product_id)
    except KeyError:
        raise HTTPException(404, f"unknown product_id {product_id}")


class AskRequest(BaseModel):
    question: str


@app.post("/api/assistant/ask")
def assistant_ask(req: AskRequest):
    """Answer a free-text question about the store from the recommendation data.
    Uses the LLM if configured, otherwise a deterministic reply. Read only."""
    return assistant.answer_question(req.question)


# ---------------------------------------------------------------------------
# Serve the built frontend (single-deploy / production).
#
# Run `npm run build` in frontend/ first; that writes frontend/dist/. If that
# folder exists we serve it here, so one server serves both the app files and
# the /api routes. In local dev this folder is absent and Vite serves the UI
# instead. Mounted LAST so it never shadows the API routes above.
# ---------------------------------------------------------------------------
_DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

if os.path.isdir(_DIST):
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="frontend")
