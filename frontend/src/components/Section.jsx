export default function Section({ title, sub, tone = "", actions, children, style }) {
  return (
    <section className="section" style={style}>
      {(title || actions) && (
        <div className={"section-head " + tone}>
          {title && <h2>{title}</h2>}
          {actions && <div className="filters">{actions}</div>}
        </div>
      )}
      {sub && <p className="sub">{sub}</p>}
      {children}
    </section>
  );
}
