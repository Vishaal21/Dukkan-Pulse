import { useState } from "react";
import { useApp, useInr } from "../store";
import Section from "../components/Section";

export default function PurchasePlan({ onNavigate }) {
  const {
    plan, recommendations, budget, updateQty, removeFromPlan, clearPlan, addToPlan,
  } = useApp();
  const inr = useInr();
  const [saved, setSaved] = useState(false);

  const reorder = recommendations?.reorder_list || [];
  const available = reorder.filter((r) => !plan.some((p) => p.product_id === r.product_id));

  const total = plan.reduce((s, p) => s + p.qty * p.unit_cost, 0);
  const remaining = budget > 0 ? budget - total : null;

  const bySupplier = plan.reduce((acc, p) => {
    const k = p.supplier_name || "Unassigned";
    acc[k] = (acc[k] || 0) + p.qty * p.unit_cost;
    return acc;
  }, {});

  async function save() {
    // The plan is already persisted to localStorage as it changes.
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <>
      <div className="page-head">
        <div className="page-head-row">
          <div>
            <h1>Purchase Plan</h1>
            <p className="sub">Review your suggested purchases before placing orders.</p>
          </div>
          <div className="filters">
            <button className="btn secondary" onClick={() => onNavigate("recommendations")}>
              Add from Recommendations
            </button>
          </div>
        </div>
      </div>

      {plan.length === 0 ? (
        <Section title="Your purchase plan is empty">
          <p className="state">Add products from Recommendations or the Budget Planner to build a plan.</p>
          <div className="filters">
            <button className="btn" onClick={() => onNavigate("recommendations")}>
              Go to Recommendations
            </button>
            <button className="btn secondary" onClick={() => onNavigate("budget")}>
              Go to Budget Planner
            </button>
          </div>
        </Section>
      ) : (
        <>
          <div className="summary-bar">
            <div className="item"><div className="k">Products</div><div className="v">{plan.length}</div></div>
            <div className="item"><div className="k">Estimated total</div><div className="v">{inr(total)}</div></div>
            {remaining !== null && (
              <div className="item">
                <div className="k">Budget remaining</div>
                <div className="v" style={{ color: remaining < 0 ? "var(--red)" : undefined }}>
                  {inr(Math.abs(remaining))}{remaining < 0 ? " over" : ""}
                </div>
              </div>
            )}
          </div>

          <Section
            title="Items to order"
            actions={
              <>
                {available.length > 0 && (
                  <select
                    aria-label="Add product from recommendations"
                    onChange={(e) => {
                      const rec = available.find((r) => r.product_id === e.target.value);
                      if (rec) addToPlan(rec);
                      e.target.value = "";
                    }}
                    defaultValue=""
                  >
                    <option value="">Add product…</option>
                    {available.map((r) => (
                      <option key={r.product_id} value={r.product_id}>
                        {r.name} (suggest {r.reorder_quantity})
                      </option>
                    ))}
                  </select>
                )}
                <button className="btn ghost small" onClick={clearPlan}>Clear plan</button>
              </>
            }
          >
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Product</th>
                    <th>Supplier</th>
                    <th className="num">Recommended</th>
                    <th className="num">Order qty</th>
                    <th className="num">Unit cost</th>
                    <th className="num">Est. total</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {plan.map((p) => {
                    const rec = reorder.find((r) => r.product_id === p.product_id);
                    return (
                      <tr key={p.product_id}>
                        <td className="prod-name">{p.name}</td>
                        <td>{p.supplier_name || "N/A"}</td>
                        <td className="num">{rec ? rec.reorder_quantity : "N/A"}</td>
                        <td className="num">
                          <input
                            type="number"
                            min="0"
                            value={p.qty}
                            onChange={(e) => updateQty(p.product_id, e.target.value)}
                            style={{ width: 80 }}
                            aria-label={`Quantity for ${p.name}`}
                          />
                        </td>
                        <td className="num">{inr(p.unit_cost)}</td>
                        <td className="num">{inr(p.qty * p.unit_cost)}</td>
                        <td className="num">
                          <button className="btn ghost small" onClick={() => removeFromPlan(p.product_id)}>
                            Remove
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Section>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }} className="plan-grid">
            <Section title="Supplier-wise totals" tone="blue">
              <table>
                <thead>
                  <tr><th>Supplier</th><th className="num">Estimated total</th></tr>
                </thead>
                <tbody>
                  {Object.entries(bySupplier).map(([s, v]) => (
                    <tr key={s}>
                      <td>{s}</td>
                      <td className="num">{inr(v)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>

            <Section title="Draft actions" tone="amber">
              <p className="small-note" style={{ marginLeft: 0 }}>
                Draft only. No order has been placed with suppliers. This is a frontend demo draft saved
                in your browser.
              </p>
              <div className="filters mt-16">
                <button className="btn" onClick={save}>Save Draft</button>
                {saved && <span className="badge ok">Draft saved</span>}
              </div>
            </Section>
          </div>
        </>
      )}

      <style>{`@media (max-width: 860px){ .plan-grid{ grid-template-columns: 1fr !important; } }`}</style>
    </>
  );
}
