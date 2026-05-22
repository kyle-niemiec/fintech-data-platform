import { formatRelative, formatTimestamp } from "../../lib/formatters";
import { useNow } from "../../lib/useNow";

export default function RelativeTime({
  iso,
}: {
  iso: string | null | undefined;
}) {
  // Subscribe to the shared clock so the elapsed label advances every second
  // even when the underlying data has not changed.
  useNow();
  return (
    <span title={formatTimestamp(iso)} className="text-navy-700">
      {formatRelative(iso)}
    </span>
  );
}
