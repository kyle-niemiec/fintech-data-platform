import { useState } from "react";
import { useCreateCdcTransaction } from "../../hooks/useCreateCdcTransaction";
import ErrorBanner from "../common/ErrorBanner";

export default function CreateCdcTransactionCard() {
  const [highRisk, setHighRisk] = useState(false);
  const mutation = useCreateCdcTransaction();

  return (
    <div className="card card-pad space-y-3">
      <div>
        <div className="text-sm font-semibold text-navy-900">
          Create CDC transaction
        </div>
        <div className="mt-1 text-sm text-navy-600">
          Insert one synthetic transaction into the OLTP database. Debezium
          streams it through the fraud-scoring pipeline. Enable{" "}
          <span className="font-medium">High risk</span> to force an AAPL trade
          over $10k, which raises a high-severity fraud alert.
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm text-navy-800">
          <input
            type="checkbox"
            checked={highRisk}
            onChange={(e) => setHighRisk(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-navy-700 focus:ring-navy-500"
          />
          High risk (fraud-shaped)
        </label>
        <button
          type="button"
          onClick={() => mutation.mutate(highRisk)}
          disabled={mutation.isPending}
          className="btn-primary"
        >
          {mutation.isPending ? "Creating…" : "Create CDC Transaction"}
        </button>
        {mutation.isSuccess ? (
          <span className="text-sm text-emerald-700">
            {mutation.data.high_risk
              ? `High-risk ${mutation.data.instrument} transaction created.`
              : `Transaction created (${mutation.data.instrument}).`}
          </span>
        ) : null}
      </div>

      {mutation.isError ? (
        <ErrorBanner
          title="Create failed"
          message={(mutation.error as Error).message}
        />
      ) : null}
    </div>
  );
}
