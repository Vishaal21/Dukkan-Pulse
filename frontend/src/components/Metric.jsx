export default function Metric({ label, value, sub, tone = "green", onClick }) {
  const content = (
    <>
      <p className="label">{label}</p>
      <p className="value">{value}</p>
      {sub && <p className="sub">{sub}</p>}
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        className={"metric clickable " + tone}
        onClick={onClick}
        title="View products"
      >
        {content}
      </button>
    );
  }
  return <div className={"metric " + tone}>{content}</div>;
}
