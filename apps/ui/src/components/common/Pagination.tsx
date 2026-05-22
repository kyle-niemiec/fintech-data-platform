import { PAGE_SIZE_OPTIONS } from "../../lib/queryKeys";

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}

/**
 * Controlled pager for the server-paginated list pages. `page` is 1-based; the
 * parent owns page/pageSize state and refetches when they change.
 */
export default function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
  onPageSizeChange,
}: Props) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, total);

  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 text-sm text-navy-600">
      <div className="flex items-center gap-2">
        <label htmlFor="page-size">Rows per page</label>
        <select
          id="page-size"
          value={pageSize}
          onChange={(e) => onPageSizeChange(Number(e.target.value))}
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-sm text-navy-900"
        >
          {PAGE_SIZE_OPTIONS.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-center gap-3">
        <span>
          {start}–{end} of {total}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="btn-ghost px-3 py-1 disabled:cursor-not-allowed disabled:opacity-40"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
          >
            Prev
          </button>
          <button
            type="button"
            className="btn-ghost px-3 py-1 disabled:cursor-not-allowed disabled:opacity-40"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
