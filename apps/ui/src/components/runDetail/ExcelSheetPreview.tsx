import type { ExcelPreview } from "../../types/api";

function renderCell(value: string | number | boolean | null) {
  if (value === null) return <span className="text-navy-400">—</span>;
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

export default function ExcelSheetPreview({ preview }: { preview: ExcelPreview }) {
  return (
    <div>
      <p className="mb-3 text-sm text-navy-500">
        First {preview.rows.length} row{preview.rows.length === 1 ? "" : "s"} of the
        uploaded workbook &mdash; sheet{" "}
        <span className="font-mono text-xs text-navy-700">{preview.sheet_name}</span>.
      </p>
      <div className="card overflow-x-auto">
        <table className="table-default">
          <thead className="bg-slate-50">
            <tr>
              {preview.columns.map((col) => (
                <th key={col}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {preview.rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} className="font-mono text-xs">
                    {renderCell(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
