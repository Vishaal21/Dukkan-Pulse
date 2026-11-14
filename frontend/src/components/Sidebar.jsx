export default function Sidebar({ items, active, onNavigate, open, onClose }) {
  return (
    <aside className={"sidebar" + (open ? " open" : "")} aria-label="Main navigation">
      <div className="brand">DukaanPulse</div>
      <nav className="nav">
        {items.map((it) => (
          <button
            key={it.id}
            className={"nav-item" + (active === it.id ? " active" : "")}
            aria-current={active === it.id ? "page" : undefined}
            onClick={() => {
              onNavigate(it.id);
              onClose?.();
            }}
          >
            {it.label}
          </button>
        ))}
      </nav>
      <div className="sidebar-foot">
        <span className="dot warn" aria-hidden="true" />
        <span>
          Demo POS data
          <br />
          (simulated, read-only)
        </span>
      </div>
    </aside>
  );
}
