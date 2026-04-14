import { formatRelative, formatTimestamp } from "../../lib/formatters";

export default function RelativeTime({
  iso,
}: {
  iso: string | null | undefined;
}) {
  return (
    <span title={formatTimestamp(iso)} className="text-navy-700">
      {formatRelative(iso)}
    </span>
  );
}
