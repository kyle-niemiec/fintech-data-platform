import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import PageContainer from "../components/layout/PageContainer";
import RunsTable from "../components/runs/RunsTable";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import PipelineFilterPills from "../components/runs/PipelineFilterPills";
import Pagination from "../components/common/Pagination";
import { useRuns } from "../hooks/useRuns";
import { PAGE_SIZE_OPTIONS } from "../lib/queryKeys";
import {
  PIPELINE_ORDER,
  pipelineColors,
  pipelineNamesFor,
  type PipelineKind,
} from "../lib/pipelineColors";

const ALLOWED = new Set<PipelineKind>(PIPELINE_ORDER);
const DEFAULT_PAGE_SIZE = 25;

interface EmptyContent {
  title: string;
  description: ReactNode;
  action?: ReactNode;
}

/** Filter-aware guidance for the empty runs list (item #1). */
function emptyStateContent(
  selected: PipelineKind[],
  backfill: boolean,
): EmptyContent {
  if (backfill) {
    return {
      title: "No backfill runs yet",
      description: "Backfill runs are produced from the Backfill page.",
      action: (
        <Link to="/backfill" className="btn-primary">
          Go to Backfill
        </Link>
      ),
    };
  }

  if (selected.length === 1) {
    const kind = selected[0];
    const label = pipelineColors[kind].label;
    if (kind === "excel") {
      return {
        title: `No ${label} runs yet`,
        description: "Trigger an Excel upload to produce a run.",
        action: (
          <Link to="/demo/upload" className="btn-primary">
            Go to Excel Upload
          </Link>
        ),
      };
    }
    if (kind === "cdc") {
      return {
        title: `No ${label} runs yet`,
        description: "Generate a CDC transaction to produce a run.",
        action: (
          <Link to="/oltp/transactions" className="btn-primary">
            Go to Transactions
          </Link>
        ),
      };
    }
    if (kind === "salesforce") {
      return {
        title: `No ${label} runs yet`,
        description:
          "Salesforce pulls run on a schedule (every 15 minutes); runs appear here automatically.",
      };
    }
    return {
      title: `No ${label} runs yet`,
      description:
        "Curated runs are produced automatically when silver/gold promotions run.",
    };
  }

  if (selected.length === 0) {
    return {
      title: "No pipeline runs yet",
      description:
        "Generate events manually on the Excel Upload or Transactions pages, or wait for the scheduled CDC and Salesforce loads.",
      action: (
        <div className="flex items-center gap-2">
          <Link to="/demo/upload" className="btn-primary">
            Go to Excel Upload
          </Link>
          <Link to="/oltp/transactions" className="btn-ghost">
            Go to Transactions
          </Link>
        </div>
      ),
    };
  }

  return {
    title: "No runs match the selected filters",
    description: "Try removing a filter to widen the results.",
  };
}

export default function RunsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selected = searchParams
    .getAll("pipeline")
    .filter((k): k is PipelineKind => ALLOWED.has(k as PipelineKind));
  const backfill = searchParams.get("backfill") === "1";

  const rawSize = Number(searchParams.get("size"));
  const pageSize = (PAGE_SIZE_OPTIONS as readonly number[]).includes(rawSize)
    ? rawSize
    : DEFAULT_PAGE_SIZE;
  const page = Math.max(1, Number(searchParams.get("page")) || 1);
  const offset = (page - 1) * pageSize;

  const update = (mutate: (params: URLSearchParams) => void) => {
    const params = new URLSearchParams(searchParams);
    mutate(params);
    setSearchParams(params, { replace: true });
  };

  const toggle = (kind: PipelineKind) => {
    const next = new Set(selected);
    if (next.has(kind)) next.delete(kind);
    else next.add(kind);
    update((params) => {
      params.delete("pipeline");
      for (const k of next) params.append("pipeline", k);
      params.delete("page");
    });
  };

  const toggleBackfill = () => {
    update((params) => {
      if (backfill) params.delete("backfill");
      else params.set("backfill", "1");
      params.delete("page");
    });
  };

  const onPageChange = (next: number) =>
    update((params) => params.set("page", String(next)));

  const onPageSizeChange = (size: number) =>
    update((params) => {
      params.set("size", String(size));
      params.delete("page");
    });

  const pipelineNames = pipelineNamesFor(selected);
  const { data, isLoading, error } = useRuns(
    pipelineNames,
    backfill,
    pageSize,
    offset,
  );

  const empty = emptyStateContent(selected, backfill);

  return (
    <PageContainer
      title="Pipeline Runs"
      description="Unified view of every pipeline run across sources, polled every 3 seconds. Use the pills to filter by pipeline."
    >
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <PipelineFilterPills selected={selected} onToggle={toggle} />
        <button
          type="button"
          aria-pressed={backfill}
          onClick={toggleBackfill}
          className={`rounded-full border px-4 py-1 text-xs font-semibold uppercase tracking-wide transition-colors ${
            backfill
              ? "border-transparent bg-violet-600 text-white"
              : "border-violet-600 bg-white text-violet-700 hover:bg-slate-50"
          }`}
        >
          Backfill
        </button>
      </div>
      {error ? (
        <ErrorBanner message={(error as Error).message} />
      ) : isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : !data || data.total === 0 ? (
        <EmptyState
          title={empty.title}
          description={empty.description}
          action={empty.action}
        />
      ) : (
        <>
          <RunsTable runs={data.items} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={data.total}
            onPageChange={onPageChange}
            onPageSizeChange={onPageSizeChange}
          />
        </>
      )}
    </PageContainer>
  );
}
