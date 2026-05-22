import PageContainer from "../components/layout/PageContainer";
import ConsumerLagTable from "../components/metrics/ConsumerLagTable";
import PipelineAnalyticsTable from "../components/metrics/PipelineAnalyticsTable";
import ErrorBanner from "../components/common/ErrorBanner";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import BusinessStory from "../components/common/BusinessStory";
import { useConsumerLag } from "../hooks/useConsumerLag";
import { usePipelineAnalytics } from "../hooks/usePipelineAnalytics";
import { businessStories } from "../lib/businessStories";
import { ApiError } from "../lib/apiClient";

export default function MetricsPage() {
  const lag = useConsumerLag();
  const analytics = usePipelineAnalytics();

  // Each section resolves to exactly one node. Skeletons are gated on the
  // initial `isPending` only, and prior data is kept across refetches, so a
  // section never toggles state on the 3-second poll (e.g. a consistently
  // unavailable consumer-lag endpoint shows a stable notice instead of flashing).
  const lagContent = lag.isPending ? (
    <LoadingSkeleton />
  ) : lag.data && lag.data.length > 0 ? (
    <ConsumerLagTable items={lag.data} />
  ) : lag.isError &&
    lag.error instanceof ApiError &&
    lag.error.status === 503 ? (
    <p className="text-sm text-navy-500">
      Redpanda Admin API unavailable. Start the full stack to see live lag data.
    </p>
  ) : lag.isError ? (
    <ErrorBanner
      title="Could not load consumer lag"
      message={(lag.error as Error).message}
    />
  ) : (
    <p className="text-sm text-navy-500">No consumer lag reported.</p>
  );

  const analyticsContent = analytics.isPending ? (
    <LoadingSkeleton />
  ) : analytics.isError ? (
    <ErrorBanner
      title="Could not load pipeline analytics"
      message={(analytics.error as Error).message}
    />
  ) : analytics.data && analytics.data.length > 0 ? (
    <PipelineAnalyticsTable items={analytics.data} />
  ) : (
    <p className="text-sm text-navy-500">
      No pipeline runs in the last 30 days.
    </p>
  );

  return (
    <PageContainer
      title="Metrics"
      description="30-day pipeline analytics and live consumer group lag read from the Redpanda broker over the Kafka protocol."
    >
      <div className="space-y-8">
        <section>
          <h2 className="mb-3 text-base font-semibold text-navy-900">
            Consumer group lag
          </h2>
          {lagContent}
        </section>

        <section>
          <h2 className="mb-3 text-base font-semibold text-navy-900">
            Pipeline analytics &mdash; last 30 days
          </h2>
          {analyticsContent}
        </section>
      </div>
      <BusinessStory {...businessStories.metrics} />
    </PageContainer>
  );
}
