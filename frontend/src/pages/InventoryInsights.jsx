import { useMemo, useState } from "react";
import { useApp, useInr } from "../store";
import { dailyRate, wholeDays } from "../format";
import Section from "../components/Section";
import DataTable from "../components/DataTable";
import StateView from "../components/StateView";

export default function InventoryInsights() {
  const { recommendations, loading, error, refresh } = useApp();
  const inr = useInr();
  const [category, setCategory] = useState("all");

  // Hooks must run unconditionally (before any early return).
  const slow = recommendations?.slow_moving || [];
  const products = recommendations?.products || [];
  const summary = recommendations?.summary || {};

  const categories = useMemo(
    () => ["all", ...Array.from(new Set(slow.map((s) => s.category).filter(Boolean)))],
    [slow]
  );
  // Overstocked but NOT slow-selling: these items sell fine, you just hold a lot.
  // Excluding slow sellers keeps this table distinct from "Slow-selling items".
  const slowIds = useMemo(() => new Set(slow.map((s) => s.product_id)), [slow]);
  const highCover = useMemo(
    () =>
      [...products]
        .filter(
          (p) =>
            !p.slow_moving &&
            !slowIds.has(p.product_id) &&
            (p.days_remaining ?? 0) >= 21 &&
            p.current_stock > 0
        )
        .sort((a, b) => (b.days_remaining ?? 0) - (a.days_remaining ?? 0))
        .slice(0, 8),
    [products, slowIds]
  );

  const slowFiltered = category === "all" ? slow : slow.filter((s) => s.category === category);
  const totalTied =
    summary.slow_moving_tied_capital ?? slow.reduce((s, m) => s + (m.tied_capital || 0), 0);

  if (loading && !recommendations) return <StateView type="loading" message="Loading inventory insights…" />;
  if (error && !recommendations)
    return <StateView type="error" message={`Could not load insights: ${error}`} onRetry={refresh} />;

  return (
    <>
      <div className="page-head">
        <h1>Inventory Insights</h1>
        <p className="sub">Find items that sell slowly and tie up your money.</p>
      </div>

      <div className="summary-bar">
        <div className="item">
          <div className="k">Slow-selling items</div>
          <div className="v">{slow.length}</div>
        </div>
        <div className="item">
          <div className="k">Money tied up</div>
          <div className="v">{inr(totalTied)}</div>
        </div>
      </div>

      <Section
        title="Slow-selling items"
        sub="These sell slowly but still hold stock, so your money sits on the shelf."
        tone="amber"
        actions={
          categories.length > 1
            ? categories.map((c) => (
                <button
                  key={c}
                  className={"filter-chip" + (category === c ? " active" : "")}
                  aria-pressed={category === c}
                  onClick={() => setCategory(c)}
                >
                  {c === "all" ? "All categories" : c}
                </button>
              ))
            : null
        }
      >
        <DataTable
          keyOf={(r) => r.product_id}
          empty="No slow-selling items found in the current demo data."
          rows={slowFiltered}
          columns={[
            { key: "name", header: "Product", render: (r) => <span className="prod-name">{r.name}</span> },
            { key: "current_stock", header: "Stock", align: "right", render: (r) => `${r.current_stock} ${r.unit}` },
            { key: "units_sold_window", header: "Units sold (30d)", align: "right", render: (r) => r.units_sold_window ?? "N/A" },
            { key: "velocity_per_day", header: "Avg daily", align: "right", render: (r) => dailyRate(r.velocity_per_day) },
            { key: "days_remaining", header: "Stock lasts (days)", align: "right", render: (r) => wholeDays(r.days_remaining) },
            { key: "tied_capital", header: "Est. value", align: "right", render: (r) => inr(r.tied_capital) },
            { key: "last_sold_date", header: "Last sold", render: (r) => r.last_sold_date || "N/A" },
          ]}
        />
        {slowFiltered.length > 0 && (
          <p className="small-note mt-16">
            You may hold more stock than your current sales need. {inr(totalTied)} is tied up in
            slow-selling stock. This is an estimate based on sales speed, not a claim that stock
            is damaged or expired.
          </p>
        )}
      </Section>

      <Section
        title="More stock than needed"
        sub="These items sell well, but you are holding more than a few weeks of stock. That is money sitting idle, not lost."
        tone="blue"
      >
        <DataTable
          keyOf={(r) => r.product_id}
          empty="No fast-selling items are overstocked in the current demo data."
          rows={highCover}
          columns={[
            { key: "name", header: "Product", render: (r) => <span className="prod-name">{r.name}</span> },
            { key: "current_stock", header: "Stock", align: "right", render: (r) => `${r.current_stock} ${r.unit}` },
            { key: "velocity_per_day", header: "Avg daily", align: "right", render: (r) => dailyRate(r.velocity_per_day) },
            { key: "days_remaining", header: "Stock lasts (days)", align: "right", render: (r) => wholeDays(r.days_remaining) },
            { key: "tied_capital", header: "Est. value", align: "right", render: (r) => inr(r.tied_capital) },
          ]}
        />
      </Section>

      <p className="small-note">{recommendations?.notice}</p>
    </>
  );
}
