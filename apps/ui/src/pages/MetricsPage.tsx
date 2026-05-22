import PageContainer from "../components/layout/PageContainer";
import ConsumerLagTable from "../components/metrics/ConsumerLagTable";
import PipelineAnalyticsTable from "../components/metrics/PipelineAnalyticsTable";
import ErrorBanner from "../components/common/ErrorBanner";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import { useConsumerLag } from "../hooks/useConsumerLag";
import { usePipelineAnalytics } from "../hooks/usePipelineAnalytics";
import { ApiError } from "../lib/apiClient";

export default function MetricsPage() {
  const lag = useConsumerLag();
  const analytics = usePipelineAnalytics();

  return (
    <PageContainer
      title="Metrics"
      description="30-day pipeline analytics and live consumer group lag from the Redpanda Admin API."
    >
      <div className="space-y-8">
        <section>
          <h2 className="mb-3 text-base font-semibold text-navy-900">
            Consumer group lag
          </h2>
          {lag.isLoading && <LoadingSkeleton />}
          {lag.isError && (
            lag.error instanceof ApiError && lag.error.status === 503 ? (
              <p className="text-sm text-navy-500">
                Redpanda Admin API unavailable. Start the full stack to see live
                lag data.
              </p>
            ) : (
              <ErrorBanner
                title="Could not load consumer lag"
                message={(lag.error as Error).message}
              />
            )
          )}
          {lag.data && <ConsumerLagTable items={lag.data} />}
        </section>

        <section>
          <h2 className="mb-3 text-base font-semibold text-navy-900">
            Pipeline analytics &mdash; last 30 days
          </h2>
          {analytics.isLoading && <LoadingSkeleton />}
          {analytics.isError && (
            <ErrorBanner
              title="Could not load pipeline analytics"
              message={(analytics.error as Error).message}
            />
          )}
          {analytics.data && analytics.data.length === 0 && (
            <p className="text-sm text-navy-500">
              No pipeline runs in the last 30 days.
            </p>
          )}
          {analytics.data && analytics.data.length > 0 && (
            <PipelineAnalyticsTable items={analytics.data} />
          )}
        </section>
      </div>
    </PageContainer>
  );
}
