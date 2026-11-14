import { api } from "../api";
import { fallbackRecommendations, fallbackBudgetPlan, DEMO_NOTICE } from "../mocks/demoData";

// Feature service for recommendations, slow-moving insights and budget plans.
// It prefers the real backend; if that is unavailable it returns deterministic
// demo fixtures flagged with `demo: true`. Screens depend only on this
// interface, so the fixture path can be removed later without UI changes.

function normalizeRecommendations(raw) {
  return {
    demo: !!raw.demo,
    notice: raw.demo ? DEMO_NOTICE : "Estimated from simulated POS data.",
    as_of: raw.as_of,
    params: raw.params || {},
    summary: raw.summary || {},
    reorder_list: raw.reorder_list || [],
    slow_moving: raw.slow_moving || [],
    products: raw.products || [],
  };
}

export const recommendationService = {
  async getRecommendations(params = "") {
    try {
      const raw = await api.recommendations(params);
      return normalizeRecommendations(raw);
    } catch {
      return normalizeRecommendations(fallbackRecommendations());
    }
  },

  async getSlowMoving() {
    const r = await this.getRecommendations();
    return { items: r.slow_moving, demo: r.demo, notice: r.notice, as_of: r.as_of };
  },

  async getBudgetPlan(budget) {
    try {
      const raw = await api.budgetPlan(budget);
      return { ...raw, demo: !!raw.demo, notice: raw.demo ? DEMO_NOTICE : "Estimated from simulated POS data." };
    } catch {
      return fallbackBudgetPlan(budget);
    }
  },

  // Detailed plain-English reason for one product (LLM if configured, else a
  // deterministic explanation from the backend).
  async getDetailedReason(productId) {
    try {
      return await api.detailedReason(productId);
    } catch {
      return { reason: "", source: "error" };
    }
  },
};

export const RISK_LABEL = {
  out_of_stock: "Out of stock",
  high: "Urgent",
  medium: "Monitor",
  low: "Low priority",
  none: "No demand",
};

export const RISK_ORDER = { out_of_stock: 0, high: 1, medium: 2, low: 3, none: 4 };
