const RISK = {
  out_of_stock: { cls: "crit", label: "Out of stock" },
  high: { cls: "crit", label: "Urgent" },
  medium: { cls: "warn", label: "Monitor" },
  low: { cls: "ok", label: "Low priority" },
  none: { cls: "neutral", label: "No demand" },
};

export default function StatusBadge({ risk, tone, children }) {
  if (tone) {
    return <span className={"badge " + tone}>{children}</span>;
  }
  const r = RISK[risk] || { cls: "neutral", label: risk || "N/A" };
  return <span className={"badge " + r.cls}>{r.label}</span>;
}

export function riskLabel(risk) {
  return (RISK[risk] || {}).label || risk || "N/A";
}
