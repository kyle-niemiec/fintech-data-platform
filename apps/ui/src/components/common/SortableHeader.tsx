import type { SortDir } from "../../lib/queryKeys";

interface Props {
  column: string;
  label: string;
  active: boolean;
  dir: SortDir;
  onSort: (column: string, nextDir: SortDir) => void;
  /** Direction applied on the first click of an inactive column. */
  initialDir?: SortDir;
  align?: "left" | "right";
}

function Caret({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="text-navy-300">↕</span>;
  return <span className="text-navy-700">{dir === "asc" ? "▲" : "▼"}</span>;
}

export default function SortableHeader({
  column,
  label,
  active,
  dir,
  onSort,
  initialDir = "asc",
  align = "left",
}: Props) {
  const nextDir: SortDir = active
    ? dir === "asc"
      ? "desc"
      : "asc"
    : initialDir;
  return (
    <th
      aria-sort={active ? (dir === "asc" ? "ascending" : "descending") : "none"}
      className={align === "right" ? "text-right" : undefined}
    >
      <button
        type="button"
        onClick={() => onSort(column, nextDir)}
        className={`inline-flex items-center gap-1 text-xs font-semibold uppercase tracking-wide transition-colors hover:text-navy-900 ${
          active ? "text-navy-900" : "text-navy-700"
        } ${align === "right" ? "flex-row-reverse" : ""}`}
      >
        <span>{label}</span>
        <Caret active={active} dir={dir} />
      </button>
    </th>
  );
}
