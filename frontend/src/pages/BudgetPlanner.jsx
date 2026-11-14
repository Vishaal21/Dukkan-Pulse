import { useEffect, useMemo, useState } from "react";
import { useApp, useInr } from "../store";
import { recommendationService } from "../services/recommendationService";
import Section from "../components/Section";
import StatusBadge from "../components/StatusBadge";
import StateView from "../components/StateView";

export default function BudgetPlanner({ onNavigate }) {
  const { budget, setBudget, addManyToPlan, plan: purchasePlan, recommendations } = useApp();
  const inr = useInr();

  const [input, setInput] = useState(budget || 10000);
  const [plan, setPlan] = useState(null);
  const [sel, setSel] = useState({}); // product_id -> {include, qty}
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function calculate(amount) {
    setBusy(true);
    setError("");
    try {
      const p = await recommendationService.getBudgetPlan(amount);
      setPlan(p);
      setBudget(Number(amount));
      const next = {};
      for (const it of p.items) next[it.product_id] = { include: true, qty: it.qty };
      setSel(next);
    } catch (e) {
      setError(String(e).replace(/^\d+:\s*/, ""));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    calculate(budget || 10000);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const chosen = useMemo(() => {
    if (!plan) return [];
    return plan.items
      .filter((it) => sel[it.product_id]?.include)
      .map((it) => ({ ...it, qty: sel[it.product_id]?.qty ?? it.qty }));
  }, [plan, sel]);

  const total = chosen.reduce((s, it) => s + it.qty * it.unit_cost, 0);
  const remaining = Number(input) - total;
  const over = remaining < 0;

  const prodById = new Map((recommendations?.products || []).map((p) => [p.product_id, p]));
  const supplierOf = (id) => prodById.get(id)?.supplier_name || "N/A";

  function toggle(id) {
    setSel((s) => ({ ...s, [id]: { ...s[id], include: !s[id].include } }));
  }
  function setQty(id, qty) {
    setSel((s) => ({ ...s, [id]: { ...s[id], qty: Math.max(0, Number(qty) || 0) } }));
  }

  function addSelected() {
    addManyToPlan(chosen.map((it) => ({
      product_id: it.product_id,
      name: it.name,
      unit: it.unit,
      supplier_id: prodById.get(it.product_id)?.supplier_id || "",
      supplier_name: supplierOf(it.product_id),
      qty: it.qty,
      unit_cost: it.unit_cost,
    })));
    onNavigate("plan");
  }

  return (
    <>
      <div className="page-head">
        <h1>Purchase Budget Planner</h1>
        <p className="sub">Plan your purchases within your available budget.</p>
      </div>

      <Section title="Available budget">
        <div className="field-row">
          <div className="field">
            <label htmlFor="budget">Available budget (INR)</label>
            <input
              id="budget"
              type="number"
              min="100"
              step="100"
              className="input"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              style={{ width: 200 }}
            />
          </div>
          <button className="btn" onClick={() => calculate(Number(input))} disabled={busy || !(Number(input) > 0)}>
            {busy ? "Calculating…" : "Calculate plan"}
          </button>
        </div>
        <p className="small-note mt-16">
          Suggestions are demo estimates, not guaranteed optimal orders. Adjust quantities to fit your budget.
        </p>
      </Section>

      {error && <StateView type="error" message={`Could not calculate plan: ${error}`} />}

      {!error && busy && !plan && <StateView type="loading" message="Calculating purchase plan…" />}

      {plan && (
        <>
          <div className={"summary-bar" + (over ? " bad" : "")}>
            <div className="item"><div className="k">Purchase cost</div><div className="v">{inr(total)}</div></div>
            <div className="item"><div className="k">Available budget</div><div className="v">{inr(input)}</div></div>
            <div className="item"><div className="k">Remaining</div><div className="v">{inr(Math.abs(remaining))}{over ? " over" : ""}</div></div>
            <div className="item"><div className="k">Products selected</div><div className="v">{chosen.length}</div></div>
          </div>

          {over && (
            <p className="small-note" style={{ color: "var(--red)", marginTop: -8 }}>
              Your selection exceeds the budget by {inr(Math.abs(remaining))}. Reduce quantities or remove items.
            </p>
          )}

          <Section title="Ranked purchase plan" sub={plan.notice} tone="green">
            {plan.items.length === 0 ? (
              <p className="state">No products currently require replenishment within this budget.</p>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Include</th>
                      <th>Product</th>
                      <th>Supplier</th>
                      <th className="num">Unit cost</th>
                      <th className="num">Qty</th>
                      <th className="num">Line total</th>
                      <th>Why</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.items.map((it) => {
                      const s = sel[it.product_id] || { include: true, qty: it.qty };
                      const line = s.qty * it.unit_cost;
                      return (
                        <tr key={it.product_id}>
                          <td>
                            <input
                              type="checkbox"
                              checked={!!s.include}
                              onChange={() => toggle(it.product_id)}
                              aria-label={`Include ${it.name}`}
                            />
                          </td>
                          <td className="prod-name">
                            {it.name}
                            {it.partial && <span className="badge warn" style={{ marginLeft: 8 }}>partial</span>}
                          </td>
                          <td>{supplierOf(it.product_id)}</td>
                          <td className="num">{inr(it.unit_cost)}</td>
                          <td className="num">
                            <input
                              type="number"
                              min="0"
                              value={s.qty}
                              onChange={(e) => setQty(it.product_id, e.target.value)}
                              style={{ width: 74 }}
                              aria-label={`Quantity for ${it.name}`}
                            />
                          </td>
                          <td className="num">{inr(line)}</td>
                          <td><StatusBadge risk={it.stockout_risk} /></td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}

            <div className="filters mt-16">
              <button className="btn" onClick={addSelected} disabled={chosen.length === 0}>
                Add selected to Purchase Plan
              </button>
              <span className="small-note">{purchasePlan.length} item(s) already in plan</span>
            </div>
          </Section>

          {plan.skipped?.length > 0 && (
            <Section title="Could not fit in budget" tone="amber">
              <p className="sub" style={{ marginLeft: 0 }}>
                These products were recommended but do not fit the budget at their minimum order quantity.
              </p>
              <ul className="action-list">
                {plan.skipped.slice(0, 8).map((s) => (
                  <li key={s.product_id} className="action-item">
                    <div className="head">
                      <div className="title">{s.name}</div>
                      <div className="nowrap muted small-note">needs {inr(s.needed_cost)}</div>
                    </div>
                    <div className="facts">
                      <span>Recommended {s.needed_qty} units · {s.stockout_risk} priority</span>
                    </div>
                  </li>
                ))}
              </ul>
            </Section>
          )}
        </>
      )}
    </>
  );
}
