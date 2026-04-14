import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import PageContainer from "../components/layout/PageContainer";
import RunSummaryHeader from "../components/runs/RunSummaryHeader";
import EventsTimeline from "../components/runDetail/EventsTimeline";
import LineageList from "../components/runDetail/LineageList";
import ArtifactsTable from "../components/runDetail/ArtifactsTable";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import { useRun } from "../hooks/useRun";

type Tab = "events" | "lineage" | "artifacts";

const TABS: { key: Tab; label: string }[] = [
  { key: "events", label: "Events" },
  { key: "lineage", label: "Lineage" },
  { key: "artifacts", label: "Artifacts" },
];

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [tab, setTab] = useState<Tab>("events");
  const { run, events, lineage, artifacts } = useRun(runId);

  if (run.error) {
    return (
      <PageContainer title="Run">
        <ErrorBanner message={(run.error as Error).message} />
        <div className="mt-4">
          <Link to="/" className="btn-ghost">
            ← Back to runs
          </Link>
        </div>
      </PageContainer>
    );
  }

  return (
    <PageContainer
      title="Run Detail"
      description={
        <>
          Full timeline, lineage, and artifact metadata for a single pipeline
          execution.
        </>
      }
      actions={
        <Link to="/" className="btn-ghost">
          ← All runs
        </Link>
      }
    >
      {run.isLoading || !run.data ? (
        <LoadingSkeleton rows={5} />
      ) : (
        <RunSummaryHeader run={run.data} />
      )}

      <div className="mt-6 flex items-center gap-1 border-b border-slate-200">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
              tab === t.key
                ? "border-navy-700 text-navy-900"
                : "border-transparent text-navy-500 hover:text-navy-800"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-5">
        {tab === "events" &&
          (events.isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : (
            <EventsTimeline events={events.data ?? []} />
          ))}
        {tab === "lineage" &&
          (lineage.isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : (
            <LineageList items={lineage.data ?? []} />
          ))}
        {tab === "artifacts" &&
          (artifacts.isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : (
            <ArtifactsTable items={artifacts.data ?? []} />
          ))}
      </div>
    </PageContainer>
  );
}
