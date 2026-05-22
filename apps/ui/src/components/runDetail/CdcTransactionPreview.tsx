import MonoId from "../common/MonoId";
import { formatTimestamp } from "../../lib/formatters";
import type { RecentTransactionItem } from "../../types/api";

function formatAmount(amount: string, instrument: string) {
  const n = Number(amount);
  if (Number.isFinite(n)) {
    return `${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${instrument}`;
  }
  return `${amount} ${instrument}`;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-navy-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm text-navy-900">{children}</dd>
    </div>
  );
}

export default function CdcTransactionPreview({
  tx,
}: {
  tx: RecentTransactionItem;
}) {
  const score = tx.risk_score != null ? Number(tx.risk_score) : null;
  const riskFlags = tx.risk_flags ?? [];
  const isManual = tx.origin === "manual_demo";
  return (
    <div className="card p-4">
      <p className="mb-4 text-sm text-navy-500">
        The OLTP transaction this CDC run scored, as shown on the Transactions
        page.
      </p>
      <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Transaction">
          <MonoId value={tx.transaction_id} short />
        </Field>
        <Field label="Account">
          <MonoId value={tx.account_id} short />
        </Field>
        <Field label="Instrument">
          <span className="font-mono text-xs">{tx.instrument}</span>
        </Field>
        <Field label="Amount">
          <span className="font-mono text-sm">
            {formatAmount(tx.amount, tx.instrument)}
          </span>
        </Field>
        <Field label="Executed">{formatTimestamp(tx.executed_at)}</Field>
        <Field label="Risk Score">
          <span className="font-mono text-xs">
            {score != null ? score.toFixed(2) : "—"}
          </span>
        </Field>
        <Field label="Flags">
          {riskFlags.length === 0 && !isManual ? (
            <span className="text-xs text-navy-400">—</span>
          ) : (
            <div className="flex flex-wrap gap-1">
              {isManual && (
                <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
                  Manual
                </span>
              )}
              {riskFlags.map((f) => (
                <span
                  key={f}
                  className="inline-flex items-center rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700"
                >
                  {f}
                </span>
              ))}
            </div>
          )}
        </Field>
      </dl>
    </div>
  );
}
