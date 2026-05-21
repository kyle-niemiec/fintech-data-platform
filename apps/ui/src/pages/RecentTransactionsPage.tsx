import PageContainer from "../components/layout/PageContainer";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import MonoId from "../components/common/MonoId";
import RelativeTime from "../components/common/RelativeTime";
import CreateCdcTransactionCard from "../components/transactions/CreateCdcTransactionCard";
import { useRecentTransactions } from "../hooks/useRecentTransactions";
import type { RecentTransactionItem } from "../types/api";

function formatAmount(amount: string, instrument: string) {
  const n = Number(amount);
  if (Number.isFinite(n)) {
    return `${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${instrument}`;
  }
  return `${amount} ${instrument}`;
}

function RiskChips({ tx }: { tx: RecentTransactionItem }) {
  if (!tx.risk_flags || tx.risk_flags.length === 0) {
    return <span className="text-xs text-navy-400">—</span>;
  }
  return (
    <div className="flex flex-wrap gap-1">
      {tx.risk_flags.map((f) => (
        <span
          key={f}
          className="inline-flex items-center rounded-full bg-rose-50 px-2 py-0.5 text-xs font-medium text-rose-700"
        >
          {f}
        </span>
      ))}
    </div>
  );
}

export default function RecentTransactionsPage() {
  const { data, isLoading, error, isFetching } = useRecentTransactions();

  return (
    <PageContainer
      title="Recent Transactions"
      description="The 25 most recent rows from the OLTP trading.transaction table, joined with their latest risk flag. Polled every 5 seconds."
    >
      <CreateCdcTransactionCard />

      {error ? (
        <ErrorBanner message={(error as Error).message} />
      ) : isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="No transactions yet"
          description="The OLTP load generator writes synthetic transactions once per minute. The first row should appear shortly."
        />
      ) : (
        <>
          <div className="card overflow-hidden">
            <table className="table-default">
              <thead className="bg-slate-50">
                <tr>
                  <th>Executed</th>
                  <th>Transaction</th>
                  <th>Account</th>
                  <th>Instrument</th>
                  <th className="text-right">Amount</th>
                  <th>Risk Score</th>
                  <th>Flags</th>
                </tr>
              </thead>
              <tbody>
                {data.map((tx) => {
                  const score = tx.risk_score != null ? Number(tx.risk_score) : null;
                  const highlighted = score != null && score >= 0.7;
                  return (
                    <tr
                      key={tx.transaction_id}
                      className={highlighted ? "bg-rose-50/60" : undefined}
                    >
                      <td>
                        <RelativeTime iso={tx.executed_at} />
                      </td>
                      <td>
                        <MonoId value={tx.transaction_id} short />
                      </td>
                      <td>
                        <MonoId value={tx.account_id} short />
                      </td>
                      <td className="font-mono text-xs">{tx.instrument}</td>
                      <td className="text-right font-mono text-sm">
                        {formatAmount(tx.amount, tx.instrument)}
                      </td>
                      <td className="font-mono text-xs">
                        {score != null ? score.toFixed(2) : "—"}
                      </td>
                      <td>
                        <RiskChips tx={tx} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="text-right text-xs text-navy-500">
            {isFetching ? "Refreshing…" : `${data.length} transaction(s)`}
          </div>
        </>
      )}
    </PageContainer>
  );
}
