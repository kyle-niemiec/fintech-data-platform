import { useState } from "react";
import { useDemoUpload } from "../../hooks/useDemoUpload";
import ErrorBanner from "../common/ErrorBanner";
import GeneratedFilePreview from "./GeneratedFilePreview";

export default function UploadCard() {
  const [rows, setRows] = useState(25);
  const mutation = useDemoUpload();

  return (
    <div className="space-y-5">
      <div className="card card-pad space-y-4">
        <div>
          <div className="text-sm font-semibold text-navy-900">
            Generate & upload payroll workbook
          </div>
          <div className="mt-1 text-sm text-navy-600">
            A randomly-selected finance demo user uploads a valid{" "}
            <span className="font-mono text-xs">payroll_v1</span> workbook to
            the landing bucket. This triggers the Excel pipeline end-to-end
            (scan → validate → bronze).
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-4">
          <label className="text-sm">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-navy-500">
              Rows
            </div>
            <input
              type="number"
              min={1}
              max={500}
              value={rows}
              onChange={(e) =>
                setRows(
                  Math.max(1, Math.min(500, Number(e.target.value) || 1)),
                )
              }
              className="w-32 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-navy-500 focus:outline-none focus:ring-1 focus:ring-navy-500"
            />
          </label>
          <button
            type="button"
            onClick={() => mutation.mutate(rows)}
            disabled={mutation.isPending}
            className="btn-primary"
          >
            {mutation.isPending ? "Uploading…" : "Generate & Upload"}
          </button>
          {mutation.isSuccess ? (
            <span className="text-sm text-emerald-700">
              Upload accepted — pipeline triggered.
            </span>
          ) : null}
        </div>
      </div>

      {mutation.isError ? (
        <ErrorBanner
          title="Upload failed"
          message={(mutation.error as Error).message}
        />
      ) : null}

      {mutation.data ? <GeneratedFilePreview result={mutation.data} /> : null}
    </div>
  );
}
