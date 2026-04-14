import { formatTimestamp } from "../../lib/formatters";
import type { RunEventItem } from "../../types/api";

export default function EventsTimeline({ events }: { events: RunEventItem[] }) {
  if (events.length === 0) {
    return (
      <div className="card card-pad text-sm text-navy-600">No events yet.</div>
    );
  }
  return (
    <ol className="card card-pad space-y-0">
      {events.map((e, idx) => {
        const last = idx === events.length - 1;
        return (
          <li key={`${e.occurred_at}-${e.event_type}`} className="relative flex gap-4 py-3">
            <div className="flex flex-col items-center">
              <div className="h-2.5 w-2.5 rounded-full bg-navy-600 ring-4 ring-navy-100" />
              {!last ? (
                <div className="mt-1 w-px flex-1 bg-slate-200" />
              ) : null}
            </div>
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-xs font-semibold text-navy-900">
                  {e.event_type}
                </span>
                <span className="text-xs text-navy-500">
                  {formatTimestamp(e.occurred_at)}
                </span>
              </div>
              {e.message ? (
                <div className="mt-1 text-sm text-navy-700">{e.message}</div>
              ) : null}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
