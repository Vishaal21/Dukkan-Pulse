import { useApp, useInr } from "../store";
import { dailyRate, dayPhrase, shortDate } from "../format";
import Metric from "../components/Metric";
import Section from "../components/Section";
import StatusBadge from "../components/StatusBadge";
import DataTable from "../components/DataTable";
import StateView from "../components/StateView";

function recText(m, inr) {
  const qty = `Order ~${m.reorder_quantity} ${m.unit} (${inr(m.reorder_cost)}).`;
  const out = shortDate(m.expected_stockout_date);
  const by = shortDate(m.order_by_date);
  let head = "No action needed right now.";
  let rest = "";
  if (m.action === "order_now") {
    head = "Order today.";
    rest = `Stock runs out around ${out}, but the supplier takes ${m.lead_time_days} days to deliver.`;
  } else if (m.action === "order_soon") {
    head = "Order within the next few days.";
    rest = `Stock runs low around ${out}.`;
  } else if (m.action === "plan_ahead") {
    head = "Comfortable for now.";
    rest = `Plan a reorder by ${by}; stock lasts until about ${out}.`;
  }
  return (
    <>
      <b>{head}</b> {rest} <b>{qty}</b>
    </>
  );
}

export default function Overview({ onNavigate }) {
  const { recommendations, loading, error, refresh } = useApp();
  const inr = useInr();

  if (loading && !recommendations) return <StateView type="loading" message="Loading business overview…" />;
  if (error && !recommendations)
    return <StateView type="error" message={`Could not load overview: ${error}`} onRetry={refresh} />;

  const summary = recommendations?.summary || {};
  const slow = recommendations?.slow_moving || [];
  const slowTiedCapital =
    summary.slow_moving_tied_capital ?? slow.reduce((s, m) => s + (m.tied_capital || 0), 0);
  // Keep the lists disjoint: slow sellers are shown once, under "Slow-selling items".
  const slowIds = new Set(slow.map((s) => s.product_id));
  const reorder = (recommendations?.reorder_list || []).filter((m) => !slowIds.has(m.product_id));
  const priority = reorder.slice(0, 5);
  const more = reorder.slice(5, 10);

  return (
    <>
      <div className="page-head">
        <h1>Business Overview</h1>
        <p className="sub">Understand what needs attention in your store.</p>
      </div>

      <div className="metrics">
        <Metric
          label="May run out"
          value={summary.at_stockout_risk ?? 0}
          sub="products"
          tone="red"
          onClick={() => onNavigate("recommendations", "urgent")}
        />
        <Metric
          label="Amount to spend"
          value={inr(summary.reorder_cost_total)}
          sub="on products to reorder"
          tone="green"
          onClick={() => onNavigate("budget")}
        />
        <Metric
          label="Slow sellers"
          value={inr(slowTiedCapital)}
          sub="money stuck"
          tone="amber"
          onClick={() => onNavigate("insights")}
        />
        <Metric
          label="Items to reorder"
          value={summary.need_reorder ?? 0}
          sub="products"
          tone="blue"
          onClick={() => onNavigate("recommendations", "all")}
        />
      </div>

      <Section
        title="Priority actions"
        sub="The most important decisions for today, from your demo data."
      >
        {priority.length === 0 ? (
          <p className="state">No products currently require attention in the demo data.</p>
        ) : (
          <ul className="action-list">
            {priority.map((m) => (
              <li className="action-item" key={m.product_id}>
                <div className="head">
                  <div className="title">
                    {m.name} <StatusBadge risk={m.stockout_risk} />
                  </div>
                  <button
                    className="btn secondary small"
                    onClick={() => onNavigate("recommendations", m.product_id)}
                  >
                    View details
                  </button>
                </div>
                <div className="facts">
                  <span>Current stock: <b>{m.current_stock} {m.unit}</b></span>
                  <span>Daily sales: <b>{dailyRate(m.velocity_per_day)}</b></span>
                  <span>Stock lasts: <b>{dayPhrase(m.days_remaining)}</b></span>
                  <span>Delivery: <b>{dayPhrase(m.lead_time_days)}</b></span>
                  <span>Order by: <b>{shortDate(m.order_by_date)}</b></span>
                </div>
                <div className="rec">{recText(m, inr)}</div>
                {m.adjustment_multiplier >= 1.1 && (
                  <div className="small-note" style={{ marginTop: 6 }}>Why more: {m.adjustment_reason}</div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }} className="overview-grid">
        <Section title="Slow-selling items" tone="amber">
          {slow.length === 0 ? (
            <p className="state">No slow-selling items found.</p>
          ) : (
            <ul className="action-list">
              {slow.slice(0, 5).map((s) => (
                <li key={s.product_id} className="action-item">
                  <div className="head">
                    <div className="title">{s.name}</div>
                    <div className="nowrap muted small-note">{inr(s.tied_capital)} tied up</div>
                  </div>
                  <div className="facts">
                    <span>{s.velocity_per_day}/day · {s.current_stock} {s.unit} in stock</span>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <button className="btn ghost small mt-16" onClick={() => onNavigate("insights")}>
            Open Inventory Insights →
          </button>
        </Section>

        <Section title="More recommendations" tone="blue">
          {more.length === 0 ? (
            <p className="state">No further purchase recommendations right now.</p>
          ) : (
            <DataTable
              keyOf={(r) => r.product_id}
              rows={more}
              columns={[
                { key: "name", header: "Product" },
                { key: "reorder_quantity", header: "Order", align: "right" },
                { key: "reorder_cost", header: "Cost", align: "right", render: (r) => inr(r.reorder_cost) },
                { key: "risk", header: "Priority", render: (r) => <StatusBadge risk={r.stockout_risk} /> },
              ]}
            />
          )}
          <button className="btn ghost small mt-16" onClick={() => onNavigate("recommendations")}>
            Open Recommendations →
          </button>
        </Section>
      </div>

      <p className="small-note">{recommendations?.notice}</p>

      <style>{`@media (max-width: 860px){ .overview-grid{ grid-template-columns: 1fr !important; } }`}</style>
    </>
  );
}
