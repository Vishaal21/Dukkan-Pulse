export default function DataTable({ columns, rows, keyOf, empty = "No data available." }) {
  if (!rows || rows.length === 0) {
    return <p className="state">{empty}</p>;
  }
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} className={c.align === "right" ? "num" : ""}>
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={keyOf ? keyOf(r) : i}>
              {columns.map((c) => (
                <td key={c.key} className={c.align === "right" ? "num" : ""}>
                  {c.render ? c.render(r) : r[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
