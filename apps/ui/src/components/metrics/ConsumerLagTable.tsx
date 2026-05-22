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

export default function ConsumerLagTable({ items }: { items: ConsumerLagItem[] }) {
  if (items.length === 0) {
    return (
      <p className="text-sm text-navy-500">
        No consumer group data returned. Groups may be idle or the admin API
        returned no assignments.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <table className="table-default">
        <thead className="bg-slate-50">
          <tr>
            <th>Group</th>
            <th>Topic</th>
            <th className="text-right">Partition</th>
            <th className="text-right">Committed</th>
            <th className="text-right">High watermark</th>
            <th className="text-right">Lag</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {items.map((item, i) => (
            <tr key={i}>
              <td className="font-mono text-xs">{item.group}</td>
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
    </div>
  );
}
