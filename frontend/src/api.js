const JSON_HEADERS = { "Content-Type": "application/json" };

// Backend origin. Empty in dev (relative paths + Vite proxy); set via
// frontend/.env (VITE_API_BASE_URL) for production. Trailing slash stripped.
const BASE = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");

async function req(url, options = {}) {
  const res = await fetch(BASE + url, options);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json();
}

export const api = {
  health: () => req("/api/health"),
  demoPosStatus: () => req("/api/demo-pos/status"),
  products: () => req("/api/pos/products"),
  inventory: () => req("/api/pos/inventory"),
  sales: (params = "") => req(`/api/pos/sales${params}`),
  suppliers: () => req("/api/pos/suppliers"),
  purchaseOrders: (params = "") => req(`/api/pos/purchase-orders${params}`),
  purchaseReceipts: (params = "") => req(`/api/pos/purchase-receipts${params}`),
  recommendations: (params = "") => req(`/api/recommendations${params}`),
  budgetPlan: (budget) => req(`/api/recommendations/budget?budget=${budget}`),
  detailedReason: (productId) =>
    req(`/api/recommendations/reason?product_id=${encodeURIComponent(productId)}`),
  askAssistant: (question) =>
    req("/api/assistant/ask", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ question }),
    }),
};
