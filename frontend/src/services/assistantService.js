// Deterministic demo assistant (no LLM). It answers the supported demo
// questions using the same recommendation data the screens use, so figures
// stay consistent across the app. Clearly labelled as a demo assistant.
import { api } from "../api";
import { dailyRate, wholeDays } from "../format";

// Ask the backend LLM (Groq) for an answer. Returns the text, or null when the
// backend has no LLM configured or the call fails, so the caller falls back to
// the deterministic answer below.
export async function askLLM(question) {
  try {
    const r = await api.askAssistant(question);
    return r && r.source === "llm" && r.answer ? r.answer : null;
  } catch {
    return null;
  }
}

const RUPEE = "₹";

function inr(n) {
  return RUPEE + Number(n).toLocaleString("en-IN");
}

function findProduct(list, name) {
  if (!name) return null;
  const q = name.toLowerCase();
  return (
    list.find((p) => p.name.toLowerCase().includes(q)) ||
    list.find((p) => q.split(/\s+/).every((w) => p.name.toLowerCase().includes(w)))
  );
}

function topReorder(recs, n = 3) {
  return [...(recs.reorder_list || [])].slice(0, n);
}

function lowStockRows(recs) {
  return (recs.products || recs.reorder_list || []).filter(
    (p) => p.stockout_risk === "high" || p.stockout_risk === "out_of_stock"
  );
}

// Returns { text, insights: [{k, v}], links: [{label, page}] }
export function answerQuestion(question, ctx) {
  const q = (question || "").toLowerCase();
  const recs = ctx.recommendations || { reorder_list: [], products: [], slow_moving: [] };

  // Budget question: "I have ₹10,000 ..."
  const amountMatch = q.match(/(?:₹|rs\.?|inr)?\s*([\d,]{3,})/);
  if ((q.includes("budget") || q.includes("have") || q.includes("purchase") || q.includes("buy")) && amountMatch) {
    const budget = Number(amountMatch[1].replace(/,/g, ""));
    const plan = ctx.budgetPlan;
    if (plan && Number(plan.budget) === budget) {
      const items = plan.items.slice(0, 3);
      return {
        text:
          `With ${inr(budget)}, your first priorities are ${items.map((i) => i.name).join(", ") || "none"}. ` +
          `This covers ${plan.item_count} product(s) for about ${inr(plan.spent)}. ` +
          `This is a demo estimate. Open the Budget Planner to fine-tune it.`,
        insights: items.map((i) => ({ k: i.name, v: `${i.qty} × ${inr(i.unit_cost)} = ${inr(i.cost)}` })),
        links: [{ label: "Open Budget Planner", page: "budget" }],
      };
    }
  }

  // Why is X urgent?
  if (q.includes("why") && (q.includes("urgent") || q.includes("low"))) {
    const nameGuess = question.replace(/why|is|urgent|\?/gi, "").trim();
    const p = findProduct(recs.products || [], nameGuess) || topReorder(recs, 1)[0];
    if (p) {
      const days = wholeDays(p.days_remaining);
      return {
        text:
          `${p.name} is a priority because you have about ${days} day(s) of stock left, ` +
          `while your supplier takes ${p.lead_time_days} day(s) to deliver. ` +
          `To avoid running out, consider ordering about ${p.reorder_quantity} ${p.unit || "units"} (${inr(p.reorder_cost)}).`,
        insights: [
          { k: "Current stock", v: `${p.current_stock} ${p.unit || ""}` },
          { k: "Sales velocity", v: `${dailyRate(p.velocity_per_day)}/day` },
          { k: "Stock lasts", v: `${days} day(s)` },
          { k: "Supplier lead time", v: `${p.lead_time_days} day(s)` },
          { k: "Order this much", v: `${p.reorder_quantity} ${p.unit || ""} · ${inr(p.reorder_cost)}` },
        ],
        links: [{ label: "View in Recommendations", page: "recommendations" }],
      };
    }
  }

  // Running low / low stock
  if (q.includes("running low") || q.includes("low stock") || q.includes("low")) {
    const rows = lowStockRows(recs);
    if (rows.length === 0) {
      return { text: "No products are currently at urgent stockout risk in the demo data.", insights: [], links: [] };
    }
    return {
      text: `${rows.length} product(s) are running low, most urgent first: ${rows.slice(0, 3).map((r) => r.name).join(", ")}.`,
      insights: rows.slice(0, 4).map((r) => ({
        k: r.name, v: `${wholeDays(r.days_remaining)} day(s) left · order ${r.reorder_quantity}`,
      })),
      links: [{ label: "View Recommendations", page: "recommendations" }],
    };
  }

  // Slow moving
  if (q.includes("slow")) {
    const slow = recs.slow_moving || [];
    if (slow.length === 0) {
      return { text: "No slow-selling items found in the current demo data.", insights: [], links: [] };
    }
    const tied = slow.reduce((s, m) => s + (m.tied_capital || 0), 0);
    return {
      text:
        `${slow.length} item(s) sell slowly and hold about ${inr(tied)} of stock. ` +
        `Review these before restocking: ${slow.slice(0, 3).map((s) => s.name).join(", ")}.`,
      insights: slow.slice(0, 4).map((s) => ({
        k: s.name, v: `${dailyRate(s.velocity_per_day)}/day · ${inr(s.tied_capital)} tied up`,
      })),
      links: [{ label: "Open Inventory Insights", page: "insights" }],
    };
  }

  // Default: what to reorder / what to buy
  const items = topReorder(recs, 3);
  if (items.length > 0) {
    const first = items[0];
    return {
      text:
        `${first.name} should be your first priority. You have about ${wholeDays(first.days_remaining)} day(s) of stock left, ` +
        `while your supplier takes ${first.lead_time_days} day(s) to deliver. ` +
        `Here are today's top reorder suggestions. (Demo assistant.)`,
      insights: items.map((i) => ({
        k: i.name, v: `order ${i.reorder_quantity} · ${inr(i.reorder_cost)} · ${wholeDays(i.days_remaining)} day(s) left`,
      })),
      links: [{ label: "View Recommendations", page: "recommendations" }],
    };
  }

  return {
    text:
      "I can help with reordering, low stock, slow-selling items and budget planning. " +
      "Try: \"What should I reorder today?\" (Demo assistant.)",
    insights: [],
    links: [],
  };
}
