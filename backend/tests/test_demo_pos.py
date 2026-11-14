"""Automated tests for the POS data foundation.

Run:  backend/.venv/bin/python -m unittest discover -s backend/tests -v
"""
import os
import sys
import unittest
from collections import defaultdict

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND)

import pos_data              # noqa: E402
import validate_pos_data     # noqa: E402
import recommendations       # noqa: E402
import main                  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


class TestDataIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = pos_data.dataset()
        cls.report = validate_pos_data.validate()

    def test_dataset_validates(self):
        self.assertTrue(self.report["ok"], self.report["errors"])

    def test_minimum_sizes(self):
        self.assertGreaterEqual(len(self.data["products"]), 30)
        self.assertLessEqual(len(self.data["products"]), 60)
        self.assertGreaterEqual(len(self.data["suppliers"]), 3)
        self.assertGreaterEqual(len(self.data["purchase_receipts"]), 30)

    def test_90_days_of_sales(self):
        days = {s["sold_date"] for s in self.data["sales"]}
        self.assertGreaterEqual(len(days), 80)

    def test_reconciliation(self):
        received = defaultdict(int)
        for r in self.data["purchase_receipts"]:
            received[r["product_id"]] += r["received_quantity"]
        sold = defaultdict(int)
        for r in self.data["sales"]:
            sold[r["product_id"]] += r["quantity"]
        adjusted = defaultdict(int)
        for r in self.data["stock_adjustments"]:
            adjusted[r["product_id"]] += r["quantity"]
        snap = {s["product_id"]: s["current_stock"] for s in self.data["inventory_snapshot"]}
        for p in self.data["products"]:
            pid = p["product_id"]
            calc = p["opening_stock"] + received[pid] - sold[pid] + adjusted[pid]
            self.assertEqual(calc, snap[pid], f"{pid} reconciliation failed")

    def test_pending_orders_not_counted_as_stock(self):
        pending = [o for o in self.data["purchase_orders"] if o["status"] == "pending"]
        self.assertGreaterEqual(len(pending), 3)
        received_ids = {r["purchase_order_id"] for r in self.data["purchase_receipts"]}
        for o in pending:
            self.assertEqual(o["received_quantity"], 0)
            self.assertEqual(o["remaining_quantity"], o["ordered_quantity"])
            self.assertNotIn(o["purchase_order_id"], received_ids)

    def test_no_negative_inventory(self):
        for s in self.data["inventory_snapshot"]:
            self.assertGreaterEqual(s["current_stock"], 0)

    def test_no_negative_or_zero_sales_qty(self):
        for s in self.data["sales"]:
            self.assertGreater(s["quantity"], 0)

    def test_unique_transaction_ids(self):
        for table, key in [("sales", "sale_id"),
                           ("purchase_receipts", "receipt_id"),
                           ("purchase_orders", "purchase_order_id"),
                           ("stock_adjustments", "adjustment_id")]:
            ids = [r[key] for r in self.data[table]]
            self.assertEqual(len(ids), len(set(ids)), f"duplicate ids in {table}")

    def test_referential_integrity(self):
        products = {p["product_id"] for p in self.data["products"]}
        suppliers = {s["supplier_id"] for s in self.data["suppliers"]}
        for s in self.data["sales"]:
            self.assertIn(s["product_id"], products)
        for r in self.data["purchase_receipts"]:
            self.assertIn(r["product_id"], products)
            self.assertIn(r["supplier_id"], suppliers)


class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(main.app)

    def _get(self, url):
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200, f"{url} -> {r.status_code}")
        return r.json()

    def test_health(self):
        self.assertEqual(self._get("/api/health")["status"], "ok")

    def test_status(self):
        d = self._get("/api/demo-pos/status")
        self.assertTrue(d["validation_ok"])
        self.assertIn("simulated", d["source"].lower())
        self.assertGreaterEqual(d["counts"]["products"], 30)

    def test_products(self):
        d = self._get("/api/pos/products")
        self.assertEqual(d["source"], "simulated_demo_pos")
        self.assertEqual(d["count"], len(d["items"]))
        self.assertGreaterEqual(d["count"], 30)

    def test_products_filter(self):
        d = self._get("/api/pos/products?category=Dairy")
        self.assertTrue(all(p["category"] == "Dairy" for p in d["items"]))

    def test_inventory(self):
        d = self._get("/api/pos/inventory")
        self.assertEqual(d["count"], len(d["items"]))
        for it in d["items"]:
            self.assertGreaterEqual(it["current_stock"], 0)

    def test_sales_filter_date_and_product(self):
        d = self._get("/api/pos/sales?limit=50")
        self.assertLessEqual(d["count"], 50)
        pid = d["items"][0]["product_id"]
        d2 = self._get(f"/api/pos/sales?product_id={pid}")
        self.assertTrue(all(s["product_id"] == pid for s in d2["items"]))

    def test_suppliers(self):
        d = self._get("/api/pos/suppliers")
        self.assertGreaterEqual(d["count"], 3)

    def test_purchase_orders_pending(self):
        d = self._get("/api/pos/purchase-orders?status=pending")
        self.assertGreaterEqual(d["count"], 3)
        self.assertTrue(all(o["status"] == "pending" for o in d["items"]))

    def test_purchase_receipts(self):
        d = self._get("/api/pos/purchase-receipts?supplier_id=SUP-01")
        self.assertTrue(all(r["supplier_id"] == "SUP-01" for r in d["items"]))

    def test_weather_endpoint_range(self):
        d = self._get("/api/pos/weather?start=2026-06-01&end=2026-06-30")
        self.assertEqual(d["count"], 30)
        for it in d["items"]:
            self.assertIn("temp_c", it)
            self.assertTrue(-5 <= it["temp_c"] <= 55)

    def test_recommendation_reason(self):
        # Force the deterministic path so tests never make a real LLM call.
        import assistant
        saved = assistant.LLM_API_KEY
        assistant.LLM_API_KEY = ""
        try:
            d = self._get("/api/recommendations/reason?product_id=P037")
        finally:
            assistant.LLM_API_KEY = saved
        self.assertIn("reason", d)
        self.assertIn(d["source"], ("llm", "demo"))
        self.assertTrue(d["reason"])
        self.assertNotIn("\u2014", d["reason"])

    def test_recommendation_reason_unknown_product(self):
        r = self.client.get("/api/recommendations/reason?product_id=NOPE")
        self.assertEqual(r.status_code, 404)

    def test_assistant_ask(self):
        # Force the deterministic path so tests never make a real LLM call.
        import assistant
        saved = assistant.LLM_API_KEY
        assistant.LLM_API_KEY = ""
        try:
            r = self.client.post("/api/assistant/ask", json={"question": "What should I reorder today?"})
        finally:
            assistant.LLM_API_KEY = saved
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn(d["source"], ("llm", "demo"))
        self.assertTrue(d["answer"])
        self.assertNotIn("\u2014", d["answer"])


class TestSeasonality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = pos_data.dataset()

    def test_weather_present_and_plausible(self):
        w = self.data["weather"]
        self.assertGreaterEqual(len(w), 300)
        self.assertTrue(all(-5 <= r["temp_c"] <= 55 for r in w))

    def test_cold_drink_sells_more_in_summer(self):
        by_pid = {p["product_id"]: p["name"] for p in self.data["products"]}
        cold = [pid for pid, n in by_pid.items() if "Coca Cola" in n][0]
        summer = sum(s["quantity"] for s in self.data["sales"]
                     if s["product_id"] == cold and s["sold_date"][5:7] in ("05", "06"))
        winter = sum(s["quantity"] for s in self.data["sales"]
                     if s["product_id"] == cold and s["sold_date"][5:7] in ("12", "01"))
        self.assertGreater(summer, winter)

    def test_tea_sells_more_in_winter(self):
        by_pid = {p["product_id"]: p["name"] for p in self.data["products"]}
        tea = [pid for pid, n in by_pid.items() if n.startswith("Tata Tea")][0]
        summer = sum(s["quantity"] for s in self.data["sales"]
                     if s["product_id"] == tea and s["sold_date"][5:7] in ("05", "06"))
        winter = sum(s["quantity"] for s in self.data["sales"]
                     if s["product_id"] == tea and s["sold_date"][5:7] in ("12", "01"))
        self.assertGreater(winter, summer)


class TestRecommendations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ov = recommendations.overview()

    def test_summary_covers_all_products(self):
        self.assertEqual(self.ov["summary"]["product_count"],
                         len(self.ov["products"]))

    def test_velocity_and_days_consistency(self):
        for m in self.ov["products"]:
            if m["velocity_per_day"] > 0:
                expected = round(m["current_stock"] / m["velocity_per_day"], 1)
                self.assertAlmostEqual(m["days_remaining"], expected, places=1)

    def test_reorder_quantities_are_moq_aligned(self):
        for m in self.ov["reorder_list"]:
            self.assertGreater(m["reorder_quantity"], 0)
            self.assertGreaterEqual(m["reorder_quantity"], m["moq"])
            self.assertEqual(m["reorder_quantity"] % m["moq"], 0)

    def test_high_risk_when_runs_out_before_delivery(self):
        for m in self.ov["products"]:
            if m["stockout_risk"] == "high":
                self.assertIsNotNone(m["days_remaining"])
                self.assertLess(m["days_remaining"], m["lead_time_days"])

    def test_slow_moving_tied_capital_matches_list(self):
        expected = round(sum(m["tied_capital"] for m in self.ov["slow_moving"]), 2)
        self.assertEqual(self.ov["summary"]["slow_moving_tied_capital"], expected)
        # it must be a subset of the whole-inventory total, never larger
        self.assertLessEqual(
            self.ov["summary"]["slow_moving_tied_capital"],
            self.ov["summary"]["tied_capital_total"],
        )

    def test_slow_movers_have_low_velocity_and_stock(self):
        self.assertGreaterEqual(len(self.ov["slow_moving"]), 1)
        for m in self.ov["slow_moving"]:
            self.assertLessEqual(m["velocity_per_day"],
                                 recommendations.SLOW_MOVING_MAX_VELOCITY)
            self.assertGreater(m["current_stock"], 0)
            self.assertGreater(m["tied_capital"], 0)

    def test_budget_plan_respects_budget(self):
        plan = recommendations.budget_plan(5000)
        self.assertEqual(round(plan["spent"] + plan["remaining"], 2), plan["budget"])
        self.assertLessEqual(plan["spent"], plan["budget"])
        self.assertEqual(round(sum(i["cost"] for i in plan["items"]), 2), plan["spent"])

    def test_budget_plan_prioritises_high_risk(self):
        plan = recommendations.budget_plan(5000)
        self.assertGreaterEqual(plan["item_count"], 1)
        ranks = [i["priority_rank"] for i in plan["items"]]
        # items are added in priority order (lowest rank number first) and the
        # first included item is the most urgent one that actually fits budget.
        self.assertEqual(ranks, sorted(ranks))
        self.assertEqual(ranks[0], min(ranks))

    def test_api_recommendations(self):
        r = TestClient(main.app).get("/api/recommendations")
        self.assertEqual(r.status_code, 200)
        self.assertIn("reorder_list", r.json())

    def test_api_budget(self):
        r = TestClient(main.app).get("/api/recommendations/budget?budget=5000")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["budget"], 5000.0)

    def test_api_budget_invalid(self):
        r = TestClient(main.app).get("/api/recommendations/budget?budget=0")
        self.assertEqual(r.status_code, 422)  # gt=0 constraint


class TestAdjustmentLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ov = recommendations.overview()
        cls.products = cls.ov["products"]

    def test_fields_present_and_bounded(self):
        for m in self.products:
            self.assertIn("baseline_reorder_quantity", m)
            self.assertIn("adjustment_multiplier", m)
            self.assertIn("adjustment_reason", m)
            self.assertTrue(m["adjustment_reason"])
            self.assertGreaterEqual(m["adjustment_multiplier"], recommendations.ADJUST_MIN)
            self.assertLessEqual(m["adjustment_multiplier"], recommendations.ADJUST_MAX)

    def test_final_ge_baseline_and_moq_aligned(self):
        for m in self.products:
            if m["baseline_reorder_quantity"] > 0:
                self.assertGreaterEqual(m["reorder_quantity"], m["baseline_reorder_quantity"])
                self.assertEqual(m["reorder_quantity"] % m["moq"], 0)

    def test_no_action_keeps_zero_baseline(self):
        for m in self.products:
            if m["action"] == "no_action":
                self.assertEqual(m["baseline_reorder_quantity"], 0)
                self.assertEqual(m["adjustment_multiplier"], 1.0)

    def test_reason_has_no_em_dash(self):
        for m in self.products:
            self.assertNotIn("\u2014", m["adjustment_reason"])

    def test_seasonal_uplift_present_in_festive_month(self):
        # "as of" November is a bigger month, so some items should be lifted.
        lifted = [m for m in self.products
                  if m["baseline_reorder_quantity"] > 0 and m["adjustment_multiplier"] > 1.1]
        self.assertGreaterEqual(len(lifted), 1)
        self.assertTrue(any("bigger month" in m["adjustment_reason"] for m in lifted))

    def test_temperature_only_for_weather_sensitive_items(self):
        for m in self.products:
            sensitive = (any(k in m["name"] for k in recommendations.COLD_DRINK_KEYS)
                         or any(k in m["name"] for k in recommendations.HOT_DRINK_KEYS)
                         or any(k in m["name"] for k in recommendations.COLD_WEATHER_KEYS))
            if not sensitive:
                self.assertNotIn("weather", m["adjustment_reason"])


if __name__ == "__main__":
    unittest.main()