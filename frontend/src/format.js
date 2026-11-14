// Display formatting helpers.

// Average daily sales as a clean whole number. Values below 1 (slow movers)
// are shown as "<1" rather than a misleading "0".
export function dailyRate(v) {
  if (v === null || v === undefined) return "N/A";
  const n = Number(v);
  if (!isFinite(n) || n <= 0) return "0";
  if (n < 1) return "<1";
  return String(Math.round(n));
}

// Round to a whole number for display.
export function whole(v) {
  if (v === null || v === undefined) return "N/A";
  return String(Math.round(Number(v)));
}

// Days of cover / days remaining, as a whole number (display only).
export function wholeDays(v) {
  if (v === null || v === undefined) return "N/A";
  return String(Math.round(Number(v)));
}

// "3 days" / "1 day" phrase for prose.
export function dayPhrase(v) {
  if (v === null || v === undefined) return "N/A";
  const n = Math.round(Number(v));
  return `${n} ${n === 1 ? "day" : "days"}`;
}

// Short date like "20 Nov" from an ISO date string.
export function shortDate(iso) {
  if (!iso) return "N/A";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

// One decimal (used for days of cover).
export function oneDecimal(v) {
  if (v === null || v === undefined) return "N/A";
  return String(v);
}
