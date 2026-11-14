// Deterministic frontend demo fixtures.
//
// These are ONLY used as a fallback when the recommendation backend is
// unreachable, so the six screens remain demonstrable offline. They are
// clearly labelled "demo prediction" in the UI. When the real recommendation
// service is available it is used instead (see recommendationService.js).

export const DEMO_NOTICE =
  "Demo prediction generated from simulated POS data. Not a live recommendation.";

// Used only if /api/recommendations is unavailable.
export function fallbackRecommendations() {
  const items = [
    { product_id: "P011", name: "Amul Milk 500ml", category: "Dairy", unit: "pouch",
      current_stock: 30, velocity_per_day: 20, days_remaining: 1.5, lead_time_days: 3,
      moq: 24, cost_price: 25, reorder_quantity: 100, reorder_cost: 2500,
      stockout_risk: "high", revenue_at_risk: 1000, supplier_name: "Sharma Distributors" },
    { product_id: "P001", name: "Maggi Noodles 70g", category: "Noodles", unit: "packet",
      current_stock: 50, velocity_per_day: 10, days_remaining: 5, lead_time_days: 3,
      moq: 24, cost_price: 12, reorder_quantity: 80, reorder_cost: 960,
      stockout_risk: "medium", revenue_at_risk: 0, supplier_name: "Gupta Traders" },
    { product_id: "P005", name: "Parle-G Biscuit 250g", category: "Biscuits", unit: "packet",
      current_stock: 200, velocity_per_day: 5, days_remaining: 40, lead_time_days: 4,
      moq: 30, cost_price: 20, reorder_quantity: 0, reorder_cost: 0,
      stockout_risk: "low", revenue_at_risk: 0, supplier_name: "Patel FMCG Supply" },
  ];
  return {
    source: "demo_fixture",
    as_of: "2026-11-14",
    demo: true,
    summary: {
      product_count: 47, need_reorder: 16, at_stockout_risk: 1, out_of_stock: 0,
      slow_moving: 7, slow_moving_tied_capital: 6720,
      tied_capital_total: 269086, reorder_cost_total: 46626,
    },
    reorder_list: items.filter((i) => i.reorder_quantity > 0),
    slow_moving: [
      { product_id: "P020", name: "Bournvita 500g", category: "Beverages", unit: "jar",
        current_stock: 19, velocity_per_day: 0.2, days_remaining: 95, tied_capital: 3990,
        last_sold_date: "2026-11-11" },
      { product_id: "P030", name: "Aashirvaad Atta 5kg", category: "Grocery", unit: "bag",
        current_stock: 13, velocity_per_day: 0.27, days_remaining: 48, tied_capital: 2730,
        last_sold_date: "2026-11-12" },
    ],
    products: items,
  };
}

// Used only if /api/recommendations/budget is unavailable.
export function fallbackBudgetPlan(budget) {
  const recs = fallbackRecommendations().reorder_list;
  let remaining = Number(budget);
  const items = [];
  const skipped = [];
  for (const m of recs) {
    const cost = m.reorder_quantity * m.cost_price;
    if (cost <= remaining) {
      items.push({ ...m, qty: m.reorder_quantity, cost, partial: false });
      remaining -= cost;
    } else {
      skipped.push({ product_id: m.product_id, name: m.name, needed_qty: m.reorder_quantity, needed_cost: cost });
    }
  }
  return {
    source: "demo_fixture",
    demo: true,
    budget: Number(budget), spent: Number(budget) - remaining, remaining,
    item_count: items.length, items, skipped,
  };
}

export const ASSISTANT_SUGGESTIONS = [
  "What should I reorder today?",
  "Which products are running low?",
  "What products are selling slowly?",
  "I have ₹10,000. What should I purchase?",
  "Why is Amul Milk urgent?",
];
