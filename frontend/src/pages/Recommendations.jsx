import { useEffect, useMemo, useRef, useState } from "react";
import { useApp, useInr } from "../store";
import { recommendationService } from "../services/recommendationService";
import { dailyRate, wholeDays, shortDate } from "../format";
import Section from "../components/Section";
import StatusBadge from "../components/StatusBadge";
import DataTable from "../components/DataTable";
import Metric from "../components/Metric";
import StateView from "../components/StateView";

const FILTERS = [
  { id: "all", label: "All" },
  { id: "urgent", label: "Urgent" },
  { id: "monitor", label: "Monitor" },
  { id: "low", label: "Low priority" },
];

function matches(filter, m) {
  if (filter === "all") return true;
  if (filter === "urgent") return m.action === "order_now";
  if (filter === "monitor") return m.action === "order_soon";
  if (filter === "low") return m.action === "plan_ahead";
  return true;
}

export default function Recommendations({ navParam, onNavigate }) {
  const { recommendations, purchaseOrders, loading, error, refresh, addToPlan, plan } = useApp();
  const inr = useInr();
  const [filter, setFilter] = useState("all");
  const [selectedId, setSelectedId] = useState(null);
  const [detailed, setDetailed] = useState(null); // { loading, text, source }
  const detailRef = useRef(null);

  useEffect(() => {
    if (!navParam) return;
    if (["all", "urgent", "monitor", "low"].includes(navParam)) {
      setFilter(navParam);
    } else {
      setSelectedId(navParam);
    }
  }, [navParam]);

  useEffect(() => {
    setDetailed(null);
  }, [selectedId]);

  const reorder = recommendations?.reorder_list || [];
  const filtered = useMemo(() => reorder.filter((m) => matches(filter, m)), [reorder, filter]);
  const selected = reorder.find((m) => m.product_id === selectedId) || null;

  // When a row is opened, bring the detail panel into view so the reason is visible.
  useEffect(() => {
    if (selected && detailRef.current) {
      detailRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  if (loading && !recommendations) return <StateView type="loading" message="Loading recommendations…" />;
  if (error && !recommendations)
    return <StateView type="error" message={`Could not load recommendations: ${error}`} onRetry={refresh} />;

  const urgent = reorder.filter((m) => m.action === "order_now").length;
  const planAhead = reorder.filter((m) => m.action === "plan_ahead").length;
  const estCost = reorder.reduce((s, m) => s + (m.reorder_cost || 0), 0);

  const pendingForSelected = selected
    ? (purchaseOrders || []).filter(
        (o) => o.product_id === selected.product_id && o.status === "pending"
      )
    : [];

  const alreadyPlanned = selected && plan.some((p) => p.product_id === selected.product_id);

  async function loadDetailedReason() {
    if (!selected) return;
    setDetailed({ loading: true });
    const r = await recommendationService.getDetailedReason(selected.product_id);
    setDetailed({ loading: false, text: (r.reason || "").replace(/\*\*/g, ""), source: r.source });
  }

  return (
    <>
      <div className="page-head">
        <h1>Purchase Recommendations</h1>
        <p className="sub">Products that may need replenishment based on your store data.</p>
      </div>

      <div className="metrics" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
        <Metric label="Order now" value={urgent} sub="runs out before delivery" tone="red" />
        <Metric label="Plan ahead" value={planAhead} sub="reorder soon" tone="amber" />
        <Metric label="Estimated cost" value={inr(estCost)} sub="to cover all suggestions" tone="green" />
      </div>

      <Section
        title="Recommended replenishment"
        sub={recommendations?.notice}
        actions={FILTERS.map((f) => (
          <button
            key={f.id}
            className={"filter-chip" + (filter === f.id ? " active" : "")}
            aria-pressed={filter === f.id}
            onClick={() => setFilter(f.id)}
          >
            {f.label}
          </button>
        ))}
      >
        <DataTable
          keyOf={(r) => r.product_id}
          empty={
            filter === "all"
              ? "No products currently require replenishment."
              : "No products match this filter."
          }
          rows={filtered}
          columns={[
            { key: "name", header: "Product", render: (r) => <span className="prod-name">{r.name}</span> },
            { key: "current_stock", header: "Stock", align: "right", render: (r) => `${r.current_stock} ${r.unit}` },
            { key: "velocity_per_day", header: "Avg daily", align: "right", render: (r) => dailyRate(r.velocity_per_day) },
            { key: "days_remaining", header: "Stock lasts (days)", align: "right", render: (r) => wholeDays(r.days_remaining) },
            { key: "order_by", header: "Order by", render: (r) => shortDate(r.order_by_date) },
            { key: "lead_time_days", header: "Delivery days", align: "right", render: (r) => `${r.lead_time_days}` },
            { key: "reorder_quantity", header: "Order this much", align: "right", render: (r) => `${r.reorder_quantity} ${r.unit}` },
            { key: "why", header: "Reason", render: (r) => (
              <button className="btn ghost small" onClick={() => setSelectedId(r.product_id)}>
                See reason
              </button>
            ) },
            { key: "reorder_cost", header: "Est. cost", align: "right", render: (r) => inr(r.reorder_cost) },
            { key: "priority", header: "Priority", render: (r) => <StatusBadge risk={r.stockout_risk} /> },
          ]}
        />
      </Section>

      {selected && (
        <div className="detail" ref={detailRef}>
          <div className="section-head">
            <h3>{selected.name}: recommendation details</h3>
            <button className="btn ghost small" onClick={() => setSelectedId(null)}>
              Close
            </button>
          </div>
          <div className="detail-grid">
            <div className="cell"><div className="k">Current stock</div><div className="v">{selected.current_stock} {selected.unit}</div></div>
            <div className="cell"><div className="k">Sales velocity</div><div className="v">{dailyRate(selected.velocity_per_day)}/day</div></div>
            <div className="cell"><div className="k">Stock lasts</div><div className="v">{wholeDays(selected.days_remaining)} days</div></div>
            <div className="cell"><div className="k">Order by</div><div className="v">{shortDate(selected.order_by_date)}</div></div>
            <div className="cell"><div className="k">Expected stockout</div><div className="v">{shortDate(selected.expected_stockout_date)}</div></div>
            <div className="cell"><div className="k">Delivery time</div><div className="v">{selected.lead_time_days} days</div></div>
            <div className="cell"><div className="k">Pending orders</div><div className="v">{pendingForSelected.length}</div></div>
            <div className="cell"><div className="k">Order this much</div><div className="v">{selected.reorder_quantity} {selected.unit}{selected.adjustment_multiplier >= 1.1 ? ` (up from ${selected.baseline_reorder_quantity})` : ""}</div></div>
            <div className="cell"><div className="k">Reason</div><div className="v">{selected.adjustment_reason || "Normal demand"}</div></div>
            <div className="cell"><div className="k">Estimated cost</div><div className="v">{inr(selected.reorder_cost)}</div></div>
            <div className="cell"><div className="k">Supplier</div><div className="v">{selected.supplier_name || "N/A"}</div></div>
          </div>
          <p className="small-note">
            {selected.action === "order_now"
              ? `At the current sales pace, stock lasts about ${wholeDays(selected.days_remaining)} day(s), which is less than the supplier's ${selected.lead_time_days}-day delivery time. This product is likely to run out before the next delivery, so order today. Order by ${shortDate(selected.order_by_date)}.`
              : selected.action === "order_soon"
              ? `Stock will run low soon (about ${wholeDays(selected.days_remaining)} day(s) left, supplier needs ${selected.lead_time_days} day(s)). Place the order within the next few days to stay safe.`
              : selected.action === "plan_ahead"
              ? `You have around ${wholeDays(selected.days_remaining)} day(s) of cover, so there is no rush. Plan a reorder by ${shortDate(selected.order_by_date)} so it arrives before stock runs out around ${shortDate(selected.expected_stockout_date)}.`
              : `Stock is comfortable for the whole planning horizon. No order is needed right now.`}
          </p>
          <div className="reason-block">
            <button className="btn secondary small" onClick={loadDetailedReason} disabled={detailed?.loading}>
              {detailed?.loading ? "Writing detailed reason…" : "See detailed reason"}
            </button>
            {detailed?.text && <p className="reason-text">{detailed.text}</p>}
            {detailed?.source === "demo" && (
              <p className="small-note">Demo explanation. No AI model is configured, this is built from your store data.</p>
            )}
            {detailed?.source === "llm" && (
              <p className="small-note">Generated by AI from your store data.</p>
            )}
            {detailed?.source === "error" && (
              <p className="small-note">Could not load the detailed reason right now.</p>
            )}
          </div>
          <div className="filters mt-16">
            <button
              className="btn"
              disabled={alreadyPlanned}
              onClick={() => addToPlan(selected)}
            >
              {alreadyPlanned ? "Added to Purchase Plan" : "Add to Purchase Plan"}
            </button>
            <button className="btn secondary" onClick={() => onNavigate("plan")}>
              Open Purchase Plan
            </button>
          </div>
        </div>
      )}
    </>
  );
}
