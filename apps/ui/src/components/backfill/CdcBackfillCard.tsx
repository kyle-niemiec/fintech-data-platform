import { useState } from "react";
import { Link } from "react-router-dom";
import { useBackfillCdc } from "../../hooks/useBackfillCdc";
import ErrorBanner from "../common/ErrorBanner";
import BackfillTargetDatePicker from "./BackfillTargetDatePicker";

const defaultDatetime = () =>
  new Date(Date.now() - 3_600_000).toISOString().slice(0, 16);

export default function CdcBackfillCard() {
  const [targetDate, setTargetDate] = useState(defaultDatetime);
  const [highRisk, setHighRisk] = useState(false);
  const [showScenario, setShowScenario] = useState(false);
  const mutation = useBackfillCdc();

  return (
    <div className="card card-pad space-y-4">
      <div>
        <div className="text-sm font-semibold text-navy-900">
          CDC transaction backfill
        </div>
        <div className="mt-1 text-sm text-navy-600">
          Use when a transaction must be posted with its original settlement
          timestamp after a late arrival or system delay.
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
            <p className="font-semibold text-slate-800">Late Settlement Posting</p>
            <p className="mt-1">
              A batch of loan disbursements settled yesterday but was delayed
              in reaching the OLTP database due to a core-banking maintenance
              window. Meridian&rsquo;s fraud team needs these transactions
              posted with their original settlement timestamps (
              <span className="font-mono">executed_at</span>) so that daily
              fraud scoring metrics are accurate and{" "}
              <span className="font-mono">loan_status_history</span> lineage
              reflects the true settlement date for regulatory reporting.
              Debezium captures the row at the current WAL LSN; the timestamp
              is data, not WAL metadata.
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <BackfillTargetDatePicker
          label="Settlement timestamp"
          value={targetDate}
          onChange={setTargetDate}
          type="datetime-local"
        />

        <label className="flex items-center gap-2 text-sm text-navy-800">
          <input
            type="checkbox"
            checked={highRisk}
            onChange={(e) => setHighRisk(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-navy-700 focus:ring-navy-500"
          />
          High-risk shape (AAPL &gt; $10k, triggers fraud alert)
        </label>

        <button
          type="button"
          disabled={!targetDate || mutation.isPending}
          onClick={() =>
            mutation.mutate({
              target_date: new Date(targetDate).toISOString(),
              high_risk: highRisk,
            })
          }
          className="btn-primary"
        >
          {mutation.isPending ? "Inserting…" : "Backfill Transaction"}
        </button>

        {mutation.isSuccess && (
          <span className="text-sm text-emerald-700">
            Transaction inserted for {new Date(mutation.data.executed_at).toLocaleDateString()}.{" "}
            <Link to="/oltp/transactions" className="underline">
              View in Recent Transactions
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
          <div className="font-semibold text-slate-800">Inserted</div>
          <div className="mt-1 grid grid-cols-2 gap-x-4 gap-y-1">
            <span className="text-slate-500">Instrument</span>
            <span className="font-mono">{mutation.data.instrument}</span>
            <span className="text-slate-500">Amount</span>
            <span className="font-mono">${mutation.data.amount}</span>
            <span className="text-slate-500">Executed at</span>
            <span className="font-mono">
              {new Date(mutation.data.executed_at).toLocaleString()}
            </span>
            <span className="text-slate-500">High risk</span>
            <span>{mutation.data.high_risk ? "Yes" : "No"}</span>
          </div>
        </div>
      )}
    </div>
  );
}
