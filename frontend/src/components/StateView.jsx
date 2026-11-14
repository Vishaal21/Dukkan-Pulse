export default function StateView({ type, message, onRetry }) {
  if (type === "loading") {
    return (
      <div className="state" aria-busy="true" aria-live="polite">
        <div className="skeleton" style={{ width: 180, height: 14, margin: "0 auto 10px" }} />
        <div className="skeleton" style={{ width: 120, height: 14, margin: "0 auto" }} />
        <p style={{ marginTop: 14 }}>{message || "Loading…"}</p>
      </div>
    );
  }
  if (type === "error") {
    return (
      <div className="state-card" role="alert">
        <p style={{ color: "var(--red)" }}>{message || "Something went wrong."}</p>
        {onRetry && (
          <button className="btn secondary" onClick={onRetry}>
            Retry
          </button>
        )}
      </div>
    );
  }
  return <p className="state">{message || "Nothing to show."}</p>;
}
