import { useState } from "react";
import { useNavigate } from "react-router-dom";
import PageContainer from "../components/layout/PageContainer";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import MonoId from "../components/common/MonoId";
import RelativeTime from "../components/common/RelativeTime";
import Pagination from "../components/common/Pagination";
import CreateCdcTransactionCard from "../components/transactions/CreateCdcTransactionCard";
import { useRecentTransactions } from "../hooks/useRecentTransactions";
import type { RecentTransactionItem } from "../types/api";

const DEFAULT_PAGE_SIZE = 25;

function formatAmount(amount: string, instrument: string) {
  const n = Number(amount);
  if (Number.isFinite(n)) {
    return `${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${instrument}`;
  }
  return `${amount} ${instrument}`;
}

function RiskChips({ tx }: { tx: RecentTransactionItem }) {
  const riskFlags = tx.risk_flags ?? [];
  const isManual = tx.origin === "manual_demo";
  if (riskFlags.length === 0 && !isManual) {
    return <span className="text-xs text-navy-400">—</span>;
  }
  return (
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
  );
}

export default function RecentTransactionsPage() {
  const navigate = useNavigate();
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useRecentTransactions(
    pageSize,
    (page - 1) * pageSize,
  );

  return (
    <PageContainer
      title="Transactions"
      description="Rows from the OLTP trading.transaction table, joined with their latest risk flag. Polled every 3 seconds."
    >
      <CreateCdcTransactionCard />

      {error ? (
        <ErrorBanner message={(error as Error).message} />
      ) : isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : !data || data.total === 0 ? (
        <EmptyState
          title="No transactions yet"
          description="The OLTP load generator writes synthetic transactions on a schedule. The first row should appear shortly."
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
                {data.items.map((tx) => {
                  const score = tx.risk_score != null ? Number(tx.risk_score) : null;
                  const highlighted = (tx.risk_flags?.length ?? 0) > 0;
                  const clickable = tx.run_id != null;
                  return (
                    <tr
                      key={tx.transaction_id}
                      onClick={
                        clickable ? () => navigate(`/runs/${tx.run_id}`) : undefined
                      }
                      title={clickable ? "View the CDC run that scored this transaction" : undefined}
                      className={[
                        highlighted ? "bg-rose-50/60" : "",
                        clickable ? "cursor-pointer" : "",
                      ]
                        .filter(Boolean)
                        .join(" ") || undefined}
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
          <Pagination
            page={page}
            pageSize={pageSize}
            total={data.total}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </>
      )}
    </PageContainer>
  );
}
