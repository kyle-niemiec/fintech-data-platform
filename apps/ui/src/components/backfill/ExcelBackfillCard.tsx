import { useState } from "react";
import { Link } from "react-router-dom";
import { useBackfillExcel } from "../../hooks/useBackfillExcel";
import ErrorBanner from "../common/ErrorBanner";
import BackfillTargetDatePicker from "./BackfillTargetDatePicker";

const defaultDate = () =>
  new Date(Date.now() - 86_400_000).toISOString().slice(0, 10);

export default function ExcelBackfillCard() {
  const [targetDate, setTargetDate] = useState(defaultDate);
  const [rows, setRows] = useState(25);
  const [dataset, setDataset] = useState<"payroll" | "commission_adjustment">(
    "commission_adjustment",
  );
  const [showScenario, setShowScenario] = useState(false);
  const mutation = useBackfillExcel();

  return (
    <div className="card card-pad space-y-4">
      <div>
        <div className="text-sm font-semibold text-navy-900">
          Excel commission backfill
        </div>
        <div className="mt-1 text-sm text-navy-600">
          Use when commission or payroll files must be ingested with their
          original effective dates after a correction or late submission.
        </div>
        <button
          type="button"
          onClick={() => setShowScenario((s) => !s)}
          className="mt-1 text-xs text-navy-400 underline-offset-2 hover:text-navy-600 hover:underline"
        >
          {showScenario ? "Hide scenario" : "View Meridian scenario"}
        </button>
        {showScenario && (
          <div className="mt-2 rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
            <p className="font-semibold text-slate-800">
              Late/Corrected Commission Adjustments
            </p>
            <p className="mt-1">
              Meridian&rsquo;s Compensation Operations team discovered that the
              March commission adjustment file for Advisor Region 7 was
              submitted with incorrect currency codes (GBP instead of USD) due
              to a spreadsheet template error. The original file was quarantined
              during validation. After the template was corrected and confirmed
              with Finance, the revised file must be backfilled with its
              original March effective dates so that{" "}
              <span className="font-mono">kpi_commission_economics</span> and
              downstream compensation reporting reflect accurate Q1 figures.
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <BackfillTargetDatePicker
          label="Target date"
          value={targetDate}
          onChange={setTargetDate}
          type="date"
        />

        <label className="text-sm">
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-navy-500">
            Dataset
          </div>
          <select
            value={dataset}
            onChange={(e) =>
              setDataset(e.target.value as "payroll" | "commission_adjustment")
            }
            className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-navy-500 focus:outline-none focus:ring-1 focus:ring-navy-500"
          >
            <option value="commission_adjustment">Commission adjustment</option>
            <option value="payroll">Payroll</option>
          </select>
        </label>

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
              setRows(Math.max(1, Math.min(500, Number(e.target.value) || 1)))
            }
            className="w-24 rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-navy-500 focus:outline-none focus:ring-1 focus:ring-navy-500"
          />
        </label>

        <button
          type="button"
          disabled={!targetDate || mutation.isPending}
          onClick={() =>
            mutation.mutate({ target_date: targetDate, rows, dataset })
          }
          className="btn-primary"
        >
          {mutation.isPending ? "Uploading…" : "Backfill Excel"}
        </button>

        {mutation.isSuccess && (
          <span className="text-sm text-emerald-700">
            Backfill triggered for {mutation.data.target_date}.{" "}
            <Link to="/runs" className="underline">
              Track in Runs Explorer
            </Link>
          </span>
        )}
      </div>

      {mutation.isError && (
        <ErrorBanner
          title="Backfill failed"
          message={(mutation.error as Error).message}
        />
      )}

      {mutation.isSuccess && (
        <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
          <div className="font-semibold text-slate-800">Triggered</div>
          <div className="mt-1 font-mono break-all">{mutation.data.object_key}</div>
          <div className="mt-1 text-slate-500">
            {mutation.data.rows} rows &middot;{" "}
            {(mutation.data.size_bytes / 1024).toFixed(1)} KB &middot; user:{" "}
            {mutation.data.demo_user}
          </div>
        </div>
      )}
    </div>
  );
}
