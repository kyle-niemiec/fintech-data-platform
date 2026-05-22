import { Link, useParams } from "react-router-dom";
import { useState } from "react";
import PageContainer from "../components/layout/PageContainer";
import RunSummaryHeader from "../components/runs/RunSummaryHeader";
import EventsTimeline from "../components/runDetail/EventsTimeline";
import LineageList from "../components/runDetail/LineageList";
import ArtifactsTable from "../components/runDetail/ArtifactsTable";
import AlertsTable from "../components/alerts/AlertsTable";
import CdcTransactionPreview from "../components/runDetail/CdcTransactionPreview";
import ExcelSheetPreview from "../components/runDetail/ExcelSheetPreview";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import BusinessStory from "../components/common/BusinessStory";
import { businessStories } from "../lib/businessStories";
import { useRun } from "../hooks/useRun";
import { useAlerts } from "../hooks/useAlerts";
import { usePreview } from "../hooks/usePreview";

type Tab = "events" | "lineage" | "artifacts" | "alerts" | "preview";

const BASE_TABS: { key: Tab; label: string }[] = [
  { key: "events", label: "Events" },
  { key: "lineage", label: "Lineage" },
  { key: "artifacts", label: "Artifacts" },
  { key: "alerts", label: "Alerts" },
];

export default function RunDetailPage() {
  const { runId = "" } = useParams();
  const [tab, setTab] = useState<Tab>("events");
  const { run, events, lineage, artifacts } = useRun(runId);
  const alerts = useAlerts(runId, undefined, 200, 0);
  const hasPreview = run.data?.preview_kind != null;
  const preview = usePreview(runId, hasPreview && tab === "preview");

  const tabs = hasPreview
    ? [...BASE_TABS, { key: "preview" as Tab, label: "Preview" }]
    : BASE_TABS;

  if (run.error) {
    return (
      <PageContainer title="Run">
        <ErrorBanner message={(run.error as Error).message} />
        <div className="mt-4">
          <Link to="/runs" className="btn-ghost">
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
        <Link to="/runs" className="btn-ghost">
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
        {tabs.map((t) => (
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
        {tab === "alerts" &&
          (alerts.isLoading ? (
            <LoadingSkeleton rows={4} />
          ) : alerts.data && alerts.data.items.length > 0 ? (
            <AlertsTable alerts={alerts.data.items} hideRun />
          ) : (
            <EmptyState
              title="No alerts for this run"
              description="This run has not raised any failure or risk alerts."
            />
          ))}
        {tab === "preview" &&
          (preview.isLoading || preview.isPending ? (
            <LoadingSkeleton rows={4} />
          ) : preview.error ? (
            <ErrorBanner message={(preview.error as Error).message} />
          ) : preview.data?.kind === "cdc_transaction" && preview.data.transaction ? (
            <CdcTransactionPreview tx={preview.data.transaction} />
          ) : preview.data?.kind === "excel" && preview.data.excel ? (
            <ExcelSheetPreview preview={preview.data.excel} />
          ) : (
            <EmptyState
              title="No preview available"
              description="This run has no previewable content."
            />
          ))}
      </div>

      <BusinessStory {...businessStories.runDetail} />
    </PageContainer>
  );
}
