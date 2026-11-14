import { api } from "../api";

// Thin wrappers over the Step 0 POS endpoints. Always returns the `items`
// array (each endpoint responds { source, count, items }).
export const posService = {
  async status() {
    return api.demoPosStatus();
  },
  async products() {
    return (await api.products()).items;
  },
  async inventory() {
    return (await api.inventory()).items;
  },
  async suppliers() {
    return (await api.suppliers()).items;
  },
  async purchaseOrders(params = "") {
    return (await api.purchaseOrders(params)).items;
  },
  async sales(params = "") {
    return (await api.sales(params)).items;
  },
};
