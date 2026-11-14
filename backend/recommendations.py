"""Smart Recommendation Engine (deterministic).

This is the analytical core of DukaanPulse. Everything here is plain,
reproducible Python - no LLM. The LLM's job (later) is only to *explain* these
numbers conversationally; React displays them.

Inputs: the read-only POS dataset (pos_data).
Outputs: per-product metrics + recommendations:
  1. Sales velocity              (units/day, recent window)
  2. Days of stock remaining     (current_stock / velocity)
  3. Stockout risk               (will it run out before the supplier delivers?)
  4. Reorder quantity            (cover lead time + target days, honour MOQ)
  5. Slow-moving products        (capital tied up in slow sellers)
  6. Budget prioritisation       (what to buy first within a budget)

All money is INR. "As of" date anchors to the latest sales date in the dataset
so results stay deterministic.
"""
import calendar
import math
from collections import defaultdict
from datetime import date, timedelta

import pos_data
from generate_demo_pos import (FESTIVALS, FESTIVAL_LEAD, FESTIVAL_TAIL, festival_multiplier,
                               COLD_DRINK_KEYS, HOT_DRINK_KEYS, COLD_WEATHER_KEYS)

ANALYSIS_WINDOW_DAYS = 30     # recent window used for sales velocity
TARGET_COVER_DAYS = 14        # days of cover to hold AFTER a delivery arrives
SAFETY_DAYS = 3               # buffer on top of supplier lead time
SLOW_MOVING_MAX_VELOCITY = 1.5   # units/day at or below -> considered slow-moving

# Adjustment layer: scale baseline reorder quantities by measured demand signals
# (month seasonality, festival windows, temperature). Clamped so we never over-order.
ADJUST_MIN = 1.0
ADJUST_MAX = 2.0
THIN_DATA_OVERALL = 1.0          # below this per-day average, fall back to category indices
FESTIVAL_LOOKAHEAD_DAYS = 50     # consider festivals up to this far ahead (covers next month)


def _anchor(data) -> date:
    dates = [s["sold_date"] for s in data["sales"]]
    return max(date.fromisoformat(d) for d in dates)


def _recent_units(data, anchor, window_days):
    start = (anchor - timedelta(days=window_days - 1)).isoformat()
    units = defaultdict(int)
    last_seen = {}
    for s in data["sales"]:
        if s["sold_date"] >= start:
            units[s["product_id"]] += s["quantity"]
        d = s["sold_date"]
        if s["product_id"] not in last_seen or d > last_seen[s["product_id"]]:
            last_seen[s["product_id"]] = d
    return units, last_seen


def _festival_days():
    """All calendar days that fall inside any festival window."""
    days = set()
    for fdate, _name, _boosts in FESTIVALS:
        d = fdate - timedelta(days=FESTIVAL_LEAD)
        end = fdate + timedelta(days=FESTIVAL_TAIL)
        while d <= end:
            days.add(d.isoformat())
            d += timedelta(days=1)
    return days


def _temp_bucket(t):
    if t < 20:
        return "cool"
    if t < 30:
        return "mild"
    return "hot"


def _context_indices(daily, dates, temp_by_date, fest_days, pid_set):
    """Measured demand indices for a set of products (a product alone, or a
    whole category). Season and temperature are measured off NON-festival days
    so they do not double-count the festival lift."""
    per_date = defaultdict(int)
    for pid in pid_set:
        for d, q in daily.get(pid, {}).items():
            per_date[d] += q

    nonfest = [d for d in dates if d not in fest_days]
    base_n = len(nonfest)
    overall_nf = (sum(per_date.get(d, 0) for d in nonfest) / base_n) if base_n else 0.0

    month_sum, month_cnt = defaultdict(int), defaultdict(int)
    temp_sum, temp_cnt = defaultdict(float), defaultdict(int)
    for d in nonfest:
        m = int(d[5:7])
        month_cnt[m] += 1
        month_sum[m] += per_date.get(d, 0)
    for d in dates:
        m = int(d[5:7])
        temp_cnt[m] += 1
        temp_sum[m] += temp_by_date[d]

    season = {}
    for m in month_cnt:
        season[m] = (month_sum[m] / month_cnt[m]) / overall_nf if overall_nf > 0 else 1.0

    bucket_sum, bucket_cnt = defaultdict(int), defaultdict(int)
    for d in nonfest:
        b = _temp_bucket(temp_by_date[d])
        bucket_sum[b] += per_date.get(d, 0)
        bucket_cnt[b] += 1
    temp_lift = {}
    for b in bucket_cnt:
        temp_lift[b] = (bucket_sum[b] / bucket_cnt[b]) / overall_nf if overall_nf > 0 else 1.0

    month_temp = {m: temp_sum[m] / temp_cnt[m] for m in temp_cnt}
    return {"overall": overall_nf, "season": season,
            "temp_lift": temp_lift, "month_temp": month_temp}


def _upcoming_festival_boost(product, anchor):
    """Calendar boost for one product from festivals in the look-ahead window.

    Returns (best_factor, [(name, days_until), ...]) only for festivals that
    actually boost this product (by category or product-name keyword), so reasons
    stay believable: chocolate is not tied to Chhath, thekua and fruits are.
    """
    lo = anchor + timedelta(days=1)
    hi = anchor + timedelta(days=FESTIVAL_LOOKAHEAD_DAYS)
    best = 1.0
    hits = []
    for fdate, name, boosts in FESTIVALS:
        f_lo = fdate - timedelta(days=FESTIVAL_LEAD)
        f_hi = fdate + timedelta(days=FESTIVAL_TAIL)
        if f_lo <= hi and f_hi >= lo:
            b = festival_multiplier(product, boosts)
            if b > 1.08:
                hits.append((name, (fdate - anchor).days))
                best = max(best, b)
    return best, hits


def _adjustment(idx, anchor, window_days, temp_sensitive, product):
    """Multiplier for the upcoming coverage window + a plain reason string.

    Temperature is only applied to genuinely weather-sensitive items (cold and
    hot drinks, blankets, heaters); otherwise it is ignored, to avoid a
    month/temperature confound. Festivals use the per-product calendar boost.
    """
    lo = anchor + timedelta(days=1)
    season, month_temp, temp_lift = idx["season"], idx["month_temp"], idx["temp_lift"]
    fest_factor, fest_hits = _upcoming_festival_boost(product, anchor)
    fest_factor = min(3.0, max(1.0, fest_factor))

    total = s_sum = t_sum = 0.0
    for k in range(1, window_days + 1):
        d = lo + timedelta(days=k - 1)
        m = d.month
        s = min(2.0, max(0.5, season.get(m, 1.0)))
        t = 1.0
        if temp_sensitive:
            t = min(2.0, max(0.5, temp_lift.get(_temp_bucket(month_temp.get(m, 25)), 1.0)))
        s_sum += s
        t_sum += t
        total += s * fest_factor * t
    n = window_days or 1
    mul = min(ADJUST_MAX, max(ADJUST_MIN, total / n))

    avg_s, avg_t = s_sum / n, t_sum / n
    tags = []
    if fest_hits and fest_factor > 1.08:
        near = [nm for nm, dd in fest_hits if dd <= 10]
        far = [nm for nm, dd in fest_hits if dd > 10]
        if near:
            tags.append(", ".join(near) + (" is close" if len(near) == 1 else " are close"))
        if far:
            tags.append(", ".join(far) + (" is coming up" if len(far) == 1 else " are coming up"))
    if avg_s > 1.08:
        tags.append(calendar.month_name[lo.month] + " is a bigger month")
    if temp_sensitive and avg_t > 1.08:
        tags.append(_temp_bucket(month_temp.get(lo.month, 25)) + " weather, demand up")
    # If the clamp left the quantity unchanged, do not claim a change.
    if mul <= ADJUST_MIN or not tags:
        return round(mul, 2), "Normal demand expected"
    return round(mul, 2), "; ".join(tags)


def product_metrics(window_days=ANALYSIS_WINDOW_DAYS, cover_days=TARGET_COVER_DAYS):
    """Compute per-product metrics. Returns a list sorted by urgency."""
    data = pos_data.dataset()
    anchor = _anchor(data)
    recent, last_seen = _recent_units(data, anchor, window_days)
    snap = data["indexes"]["snapshot_by_product"]
    sup = data["indexes"]["supplier_by_id"]

    # --- demand-signal context (measured once, then reused per product) ---
    dates = [w["date"] for w in data["weather"]]
    temp_by_date = {w["date"]: w["temp_c"] for w in data["weather"]}
    fest_days = _festival_days()
    daily = defaultdict(lambda: defaultdict(int))
    for s0 in data["sales"]:
        daily[s0["product_id"]][s0["sold_date"]] += s0["quantity"]
    cat_members = defaultdict(set)
    for p in data["products"]:
        cat_members[p["category"]].add(p["product_id"])
    prod_idx = {p["product_id"]: _context_indices(daily, dates, temp_by_date, fest_days, {p["product_id"]})
                for p in data["products"]}
    cat_idx = {c: _context_indices(daily, dates, temp_by_date, fest_days, ids)
               for c, ids in cat_members.items()}

    out = []
    for p in data["products"]:
        pid = p["product_id"]
        stock = snap.get(pid, {}).get("current_stock", 0)
        units = recent.get(pid, 0)
        velocity = round(units / window_days, 1)

        s = sup.get(p["supplier_id"], {})
        lead = int(s.get("standard_lead_time_days", 0) or 0)
        moq = int(s.get("minimum_order_quantity", 1) or 1)
        cost = float(p["cost_price"])
        sell = float(p["selling_price"])

        days_remaining = round(stock / velocity, 1) if velocity > 0 else None

        # --- stockout risk ---
        if velocity <= 0:
            risk = "none"
        elif stock <= 0:
            risk = "out_of_stock"
        elif days_remaining < lead:
            risk = "high"
        elif days_remaining < lead + SAFETY_DAYS:
            risk = "medium"
        else:
            risk = "low"

        # --- reorder quantity ---
        reorder_point = math.ceil(velocity * (lead + SAFETY_DAYS))
        target_stock = velocity * (lead + cover_days)
        needed = max(0, math.ceil(target_stock - stock)) if velocity > 0 else 0
        reorder_quantity = 0
        if needed > 0:
            reorder_quantity = max(moq, int(math.ceil(needed / moq) * moq))
        reorder_cost = round(reorder_quantity * cost, 2)

        # --- adjustment layer: scale by measured month / festival / temperature ---
        baseline_reorder_quantity = reorder_quantity
        adjustment_multiplier = 1.0
        adjustment_reason = "Normal demand expected"
        if baseline_reorder_quantity > 0:
            idx = prod_idx[pid] if prod_idx[pid]["overall"] >= THIN_DATA_OVERALL else cat_idx[p["category"]]
            window = max(1, min(60, lead + cover_days))
            temp_sensitive = (any(k in p["name"] for k in COLD_DRINK_KEYS)
                              or any(k in p["name"] for k in HOT_DRINK_KEYS)
                              or any(k in p["name"] for k in COLD_WEATHER_KEYS))
            adjustment_multiplier, adjustment_reason = _adjustment(
                idx, anchor, window, temp_sensitive, p)
            reorder_quantity = int(math.ceil(baseline_reorder_quantity * adjustment_multiplier / moq) * moq)
            reorder_cost = round(reorder_quantity * cost, 2)

        # units likely lost during a stockout (before delivery), if any
        shortfall_units = 0
        if velocity > 0 and days_remaining is not None and days_remaining < lead:
            shortfall_units = int(round((lead - days_remaining) * velocity))
        revenue_at_risk = round(shortfall_units * sell, 2)

        tied_capital = round(stock * cost, 2)

        # --- action & timing ---
        #   order_now   : will run out before the next delivery arrives
        #   order_soon  : inside the safety buffer
        #   plan_ahead  : comfortable now, but a reorder should be planned
        #   no_action   : well covered for the whole horizon
        if velocity <= 0:
            action = "no_action"
        elif days_remaining <= lead:
            action = "order_now"
        elif days_remaining <= lead + SAFETY_DAYS:
            action = "order_soon"
        elif days_remaining <= lead + cover_days:
            action = "plan_ahead"
        else:
            action = "no_action"

        if velocity > 0 and days_remaining is not None:
            expected_stockout_date = (anchor + timedelta(days=int(round(days_remaining)))).isoformat()
            order_by_date = (anchor + timedelta(days=max(0, int(round(days_remaining - lead))))).isoformat()
        else:
            expected_stockout_date = None
            order_by_date = None

        out.append({
            "product_id": pid,
            "sku": p["sku"],
            "name": p["name"],
            "category": p["category"],
            "unit": p["unit"],
            "supplier_id": p["supplier_id"],
            "supplier_name": s.get("supplier_name"),
            "lead_time_days": lead,
            "moq": moq,
            "cost_price": cost,
            "selling_price": sell,
            "current_stock": stock,
            "units_sold_window": units,
            "velocity_per_day": velocity,
            "days_remaining": days_remaining,
            "last_sold_date": last_seen.get(pid),
            "reorder_point": reorder_point,
            "reorder_quantity": reorder_quantity,
            "baseline_reorder_quantity": baseline_reorder_quantity,
            "adjustment_multiplier": adjustment_multiplier,
            "adjustment_reason": adjustment_reason,
            "reorder_cost": reorder_cost,
            "stockout_risk": risk,
            "action": action,
            "order_by_date": order_by_date,
            "expected_stockout_date": expected_stockout_date,
            "revenue_at_risk": revenue_at_risk,
            "tied_capital": tied_capital,
            "slow_moving": velocity <= SLOW_MOVING_MAX_VELOCITY,
        })

    out.sort(key=lambda m: (m["days_remaining"] if m["days_remaining"] is not None else 1e9,
                            -m["velocity_per_day"]))
    return out, anchor


_RISK_RANK = {"out_of_stock": 4, "high": 3, "medium": 2, "low": 1, "none": 0}
_ACTION_RANK = {"order_now": 3, "order_soon": 2, "plan_ahead": 1, "no_action": 0}


def reorder_recommendations(window_days=ANALYSIS_WINDOW_DAYS, cover_days=TARGET_COVER_DAYS):
    """Products that should be reordered, ordered by purchase priority.
    Only products with a real action (order_now / order_soon / plan_ahead)."""
    metrics, anchor = product_metrics(window_days, cover_days)
    needs = [m for m in metrics if m["action"] in ("order_now", "order_soon", "plan_ahead")]

    def priority(m):
        return (_ACTION_RANK[m["action"]],
                m.get("adjustment_multiplier", 1.0),
                m["revenue_at_risk"],
                -(m["days_remaining"] if m["days_remaining"] is not None else 1e9))

    needs.sort(key=priority, reverse=True)
    for i, m in enumerate(needs, 1):
        m["priority_rank"] = i
    return needs, metrics, anchor


def slow_moving_products(max_velocity=SLOW_MOVING_MAX_VELOCITY):
    """Products with sales at/below `max_velocity` that still hold stock,
    i.e. money tied up. Sorted by capital tied up (desc)."""
    metrics, anchor = product_metrics()
    slow = [m for m in metrics
            if m["slow_moving"] and m["current_stock"] > 0
            and m["velocity_per_day"] <= max_velocity]
    slow.sort(key=lambda m: m["tied_capital"], reverse=True)
    return slow, anchor


def budget_plan(budget, window_days=ANALYSIS_WINDOW_DAYS, cover_days=TARGET_COVER_DAYS):
    """Allocate a purchase budget across recommended items by priority.

    Greedy: walk items from highest priority, buy the full recommended quantity
    if the budget allows, otherwise buy a partial (MOQ-aligned) quantity; skip
    anything that no longer fits.
    """
    budget = float(budget)
    if budget <= 0:
        raise ValueError("budget must be greater than 0")

    needs, _, anchor = reorder_recommendations(window_days, cover_days)
    remaining = budget
    items, skipped = [], []

    for m in needs:
        qty = m["reorder_quantity"]
        unit = m["cost_price"]
        full_cost = round(qty * unit, 2)

        if full_cost <= remaining:
            items.append({
                "product_id": m["product_id"], "name": m["name"],
                "unit": m["unit"], "qty": qty, "unit_cost": unit,
                "cost": full_cost, "priority_rank": m["priority_rank"],
                "stockout_risk": m["stockout_risk"],
                "days_remaining": m["days_remaining"], "partial": False,
            })
            remaining = round(remaining - full_cost, 2)
        else:
            moq = m["moq"]
            max_qty = int(remaining // unit)
            partial_qty = (max_qty // moq) * moq
            if partial_qty >= moq:
                cost = round(partial_qty * unit, 2)
                items.append({
                    "product_id": m["product_id"], "name": m["name"],
                    "unit": m["unit"], "qty": partial_qty, "unit_cost": unit,
                    "cost": cost, "priority_rank": m["priority_rank"],
                    "stockout_risk": m["stockout_risk"],
                    "days_remaining": m["days_remaining"], "partial": True,
                })
                remaining = round(remaining - cost, 2)
            else:
                skipped.append({
                    "product_id": m["product_id"], "name": m["name"],
                    "needed_qty": qty, "needed_cost": full_cost,
                    "stockout_risk": m["stockout_risk"],
                })

    spent = round(budget - remaining, 2)
    return {
        "as_of": anchor.isoformat(),
        "budget": round(budget, 2),
        "spent": spent,
        "remaining": round(remaining, 2),
        "item_count": len(items),
        "items": items,
        "skipped": skipped,
    }


def overview(window_days=ANALYSIS_WINDOW_DAYS, cover_days=TARGET_COVER_DAYS):
    """Full recommendation payload: summary + reorder list + slow movers."""
    needs, metrics, anchor = reorder_recommendations(window_days, cover_days)
    slow = [m for m in metrics if m["slow_moving"] and m["current_stock"] > 0]
    slow.sort(key=lambda m: m["tied_capital"], reverse=True)

    at_risk = [m for m in metrics if m["action"] == "order_now"]
    counts = {
        a: sum(1 for m in metrics if m["action"] == a)
        for a in ("order_now", "order_soon", "plan_ahead", "no_action")
    }
    return {
        "as_of": anchor.isoformat(),
        "params": {
            "analysis_window_days": window_days,
            "target_cover_days": cover_days,
            "safety_days": SAFETY_DAYS,
            "slow_moving_max_velocity": SLOW_MOVING_MAX_VELOCITY,
        },
        "summary": {
            "product_count": len(metrics),
            "need_reorder": counts["order_now"] + counts["order_soon"] + counts["plan_ahead"],
            "urgent": counts["order_now"],
            "monitor": counts["order_soon"],
            "plan_ahead": counts["plan_ahead"],
            "no_action": counts["no_action"],
            "at_stockout_risk": len(at_risk),
            "out_of_stock": sum(1 for m in metrics if m["stockout_risk"] == "out_of_stock"),
            "slow_moving": len(slow),
            # capital tied up in slow-moving stock only (matches the slow_moving list)
            "slow_moving_tied_capital": round(sum(m["tied_capital"] for m in slow), 2),
            # capital tied up in ALL current stock at cost (whole inventory, not just slow movers)
            "tied_capital_total": round(sum(m["tied_capital"] for m in metrics), 2),
            "reorder_cost_total": round(sum(m["reorder_cost"] for m in needs), 2),
        },
        "reorder_list": needs,
        "slow_moving": slow,
        "products": metrics,
    }
