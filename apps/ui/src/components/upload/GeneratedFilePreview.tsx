import { formatBytes, formatTimestamp } from "../../lib/formatters";
import DemoUserBadge from "./DemoUserBadge";
import type { DemoUploadResponse } from "../../types/api";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5">
      <div className="text-[11px] font-semibold uppercase tracking-wide text-navy-500">
        {label}
      </div>
      <div className="min-w-0 flex-1 text-right">{children}</div>
    </div>
  );
}

export default function GeneratedFilePreview({
  result,
}: {
  result: DemoUploadResponse;
}) {
  return (
    <div className="card card-pad space-y-1">
      <Row label="Uploader">
        <DemoUserBadge email={result.demo_user} />
      </Row>
      <Row label="Bucket">
        <span className="font-mono text-xs">{result.bucket}</span>
      </Row>
      <Row label="Object key">
        <span className="break-all font-mono text-xs text-navy-800">
          {result.object_key}
        </span>
      </Row>
      <Row label="Rows">{result.rows}</Row>
      <Row label="Size">{formatBytes(result.size_bytes)}</Row>
      <Row label="Generated">
        <span className="text-xs text-navy-700">
          {formatTimestamp(result.generated_at)}
        </span>
      </Row>
      <Row label="Trigger ref">
        <span className="break-all font-mono text-xs text-navy-800">
          {result.run_trigger_ref}
        </span>
      </Row>
    </div>
  );
}
