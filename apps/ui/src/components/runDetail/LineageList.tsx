import StageBadge from "../common/StageBadge";
import { formatTimestamp } from "../../lib/formatters";
import type { LineageTrailItem } from "../../types/api";

function UriList({ title, uris }: { title: string; uris: string[] }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-navy-500">
        {title}
      </div>
      {uris.length === 0 ? (
        <div className="text-xs text-slate-400">—</div>
      ) : (
        <ul className="mt-0.5 space-y-0.5 break-all font-mono text-xs text-navy-800">
          {uris.map((u) => (
            <li key={u}>{u}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function LineageList({ items }: { items: LineageTrailItem[] }) {
  if (items.length === 0) {
    return (
      <div className="card card-pad text-sm text-navy-600">
        No lineage recorded yet.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div key={item.event_id} className="card card-pad">
          <div className="flex flex-wrap items-center gap-2">
            <StageBadge stage={item.stage} />
            <span className="font-mono text-xs text-navy-700">
              {item.event_type}
            </span>
            <span className="text-xs text-navy-500">
              {formatTimestamp(item.occurred_at)}
            </span>
            <div className="ml-auto text-xs text-navy-600">
              <span className="font-mono">
                {item.transform_id ?? "—"}
                {item.transform_version ? ` @ ${item.transform_version}` : ""}
              </span>
            </div>
          </div>
          <div className="mt-3 grid gap-4 md:grid-cols-2">
            <UriList title="Inputs" uris={item.input_uris} />
            <UriList title="Outputs" uris={item.output_uris} />
          </div>
        </div>
      ))}
    </div>
  );
}
