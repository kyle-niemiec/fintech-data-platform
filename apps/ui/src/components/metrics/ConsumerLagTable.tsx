import { useState } from "react";
import type { ConsumerLagItem } from "../../types/api";

function LagDot({ lag }: { lag: number }) {
  const cls =
    lag === 0
      ? "bg-emerald-500"
      : lag < 100
        ? "bg-amber-400"
        : "bg-rose-500";
  return <span className={`inline-block h-2 w-2 rounded-full ${cls}`} />;
}

interface LagGroup {
  group: string;
  rows: ConsumerLagItem[];
  totalLag: number;
}

function groupByConsumerGroup(items: ConsumerLagItem[]): LagGroup[] {
  const byGroup = new Map<string, ConsumerLagItem[]>();
  for (const item of items) {
    const rows = byGroup.get(item.group);
    if (rows) {
      rows.push(item);
    } else {
      byGroup.set(item.group, [item]);
    }
  }
  return Array.from(byGroup, ([group, rows]) => ({
    group,
    rows,
    totalLag: rows.reduce((sum, r) => sum + r.lag, 0),
  }));
}

export default function ConsumerLagTable({ items }: { items: ConsumerLagItem[] }) {
  const groups = groupByConsumerGroup(items);
  // Default expanded: every group starts open.
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  if (items.length === 0) {
    return (
      <p className="text-sm text-navy-500">
        No consumer group data returned. Groups may be idle or the admin API
        returned no assignments.
      </p>
    );
  }

  const toggle = (group: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(group)) {
        next.delete(group);
      } else {
        next.add(group);
      }
      return next;
    });

  return (
    <div className="space-y-3">
      {groups.map(({ group, rows, totalLag }) => {
        const isOpen = !collapsed.has(group);
        return (
          <div
            key={group}
            className="overflow-hidden rounded-lg border border-slate-200"
          >
            <button
              type="button"
              onClick={() => toggle(group)}
              aria-expanded={isOpen}
              className="flex w-full items-center justify-between bg-slate-50 px-4 py-2.5 text-left hover:bg-slate-100"
            >
              <span className="flex items-center gap-2">
                <span className="text-navy-400">{isOpen ? "▾" : "▸"}</span>
                <span className="font-mono text-xs font-semibold text-navy-900">
                  {group}
                </span>
                <span className="text-xs text-navy-500">
                  {rows.length} partition{rows.length === 1 ? "" : "s"}
                </span>
              </span>
              <span className="flex items-center gap-2 text-xs">
                <span className="font-medium text-navy-500">total lag</span>
                <span className="font-mono font-semibold text-navy-900">
                  {totalLag}
                </span>
                <LagDot lag={totalLag} />
              </span>
            </button>
            {isOpen && (
              <table className="table-default">
                <thead className="bg-white">
                  <tr>
                    <th>Topic</th>
                    <th className="text-right">Partition</th>
                    <th className="text-right">Committed</th>
                    <th className="text-right">High watermark</th>
                    <th className="text-right">Lag</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((item, i) => (
                    <tr key={i}>
                      <td className="font-mono text-xs">{item.topic}</td>
                      <td className="text-right font-mono text-xs">{item.partition}</td>
                      <td className="text-right font-mono text-xs">{item.current_offset}</td>
                      <td className="text-right font-mono text-xs">{item.log_end_offset}</td>
                      <td className="text-right font-mono text-xs font-semibold">{item.lag}</td>
                      <td className="text-center">
                        <LagDot lag={item.lag} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        );
      })}
    </div>
  );
}
