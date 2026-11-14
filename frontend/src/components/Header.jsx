import { useApp } from "../store";

export default function Header({ title, onMenu }) {
  const { status, loading, refresh } = useApp();
  const ok = status?.validation_ok;
  const snapshot = status?.generated_at || status?.period?.end;
  const storeName = "Demo Store";

  return (
    <header className="header">
      <div className="header-left">
        <button
          className="btn ghost hamburger"
          aria-label="Open navigation"
          onClick={onMenu}
        >
          ☰
        </button>
        <div>
          <div className="store">{storeName}</div>
          <div className="meta">
            <span>
              <span className={"dot " + (!status ? "wait" : ok ? "" : "bad")} aria-hidden="true" />{" "}
              {!status
                ? "Connecting…"
                : ok
                ? "Demo POS data connected"
                : "POS data issue"}
            </span>
            {snapshot && <span>Snapshot: {String(snapshot).replace("T", " ")}</span>}
            {title && <span>{title}</span>}
          </div>
        </div>
      </div>
      <div className="header-actions">
        <button className="btn secondary" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>
    </header>
  );
}
