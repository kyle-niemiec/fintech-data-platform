import PageContainer from "../components/layout/PageContainer";
import ExcelBackfillCard from "../components/backfill/ExcelBackfillCard";
import CdcBackfillCard from "../components/backfill/CdcBackfillCard";

export default function BackfillPage() {
  return (
    <PageContainer
      title="Backfill & Replay"
      description="Generate synthetic historical data and run it through the full pipeline. Each backfill creates a traceable pipeline run visible in the Runs Explorer."
    >
      <div className="space-y-5">
        <ExcelBackfillCard />
        <CdcBackfillCard />
      </div>
    </PageContainer>
  );
}
