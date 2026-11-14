import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { posService } from "./services/posService";
import { recommendationService } from "./services/recommendationService";

const AppContext = createContext(null);

const LS_PLAN = "dukaanpulse.plan";
const LS_BUDGET = "dukaanpulse.budget";

function readPlan() {
  try {
    return JSON.parse(localStorage.getItem(LS_PLAN)) || [];
  } catch {
    return [];
  }
}

export function AppProvider({ children }) {
  const [data, setData] = useState({
    status: null,
    products: [],
    inventory: [],
    suppliers: [],
    purchaseOrders: [],
    recommendations: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const [plan, setPlan] = useState(readPlan);
  const [budget, setBudget] = useState(() => {
    const b = localStorage.getItem(LS_BUDGET);
    return b ? Number(b) : 0;
  });

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [status, products, inventory, suppliers, purchaseOrders, recommendations] =
        await Promise.all([
          posService.status(),
          posService.products(),
          posService.inventory(),
          posService.suppliers(),
          posService.purchaseOrders(),
          recommendationService.getRecommendations(),
        ]);
      setData({ status, products, inventory, suppliers, purchaseOrders, recommendations });
    } catch (e) {
      setError(String(e).replace(/^\d+:\s*/, ""));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const refresh = useCallback(() => setRefreshKey((k) => k + 1), []);

  // ---- purchase plan actions ----
  const persist = (next) => {
    setPlan(next);
    try {
      localStorage.setItem(LS_PLAN, JSON.stringify(next));
    } catch {
      /* ignore */
    }
  };

  const addToPlan = useCallback((rec, qty) => {
    setPlan((prev) => {
      if (prev.some((p) => p.product_id === rec.product_id)) return prev;
      const next = [
        ...prev,
        {
          product_id: rec.product_id,
          name: rec.name,
          unit: rec.unit || "",
          supplier_id: rec.supplier_id || "",
          supplier_name: rec.supplier_name || "N/A",
          qty: qty || rec.reorder_quantity || 1,
          unit_cost: rec.cost_price ?? rec.unit_cost ?? 0,
        },
      ];
      try {
        localStorage.setItem(LS_PLAN, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const addManyToPlan = useCallback((recs) => {
    setPlan((prev) => {
      const have = new Set(prev.map((p) => p.product_id));
      const add = recs
        .filter((r) => !have.has(r.product_id))
        .map((r) => ({
          product_id: r.product_id,
          name: r.name,
          unit: r.unit || "",
          supplier_id: r.supplier_id || "",
          supplier_name: r.supplier_name || "N/A",
          qty: r.qty || r.reorder_quantity || 1,
          unit_cost: r.unit_cost ?? r.cost_price ?? 0,
        }));
      const next = [...prev, ...add];
      try {
        localStorage.setItem(LS_PLAN, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const updateQty = useCallback((productId, qty) => {
    const q = Math.max(0, Number(qty) || 0);
    persist(plan.map((p) => (p.product_id === productId ? { ...p, qty: q } : p)));
  }, [plan]);

  const removeFromPlan = useCallback(
    (productId) => persist(plan.filter((p) => p.product_id !== productId)),
    [plan]
  );

  const clearPlan = useCallback(() => persist([]), []);

  const saveBudget = useCallback((b) => {
    setBudget(b);
    try {
      localStorage.setItem(LS_BUDGET, String(b));
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo(
    () => ({
      ...data,
      loading,
      error,
      refresh,
      plan,
      budget,
      setBudget: saveBudget,
      addToPlan,
      addManyToPlan,
      updateQty,
      removeFromPlan,
      clearPlan,
      productsById: new Map(data.products.map((p) => [p.product_id, p])),
      suppliersById: new Map(data.suppliers.map((s) => [s.supplier_id, s])),
      inventoryById: new Map(data.inventory.map((i) => [i.product_id, i])),
    }),
    [data, loading, error, refresh, plan, budget, saveBudget, addToPlan, addManyToPlan, updateQty, removeFromPlan, clearPlan]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}

export function useInr() {
  return useCallback(
    (n) =>
      "₹" +
      Number(n || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 }),
    []
  );
}
