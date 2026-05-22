import PageContainer from "../components/layout/PageContainer";
import UploadCard from "../components/upload/UploadCard";
import BusinessStory from "../components/common/BusinessStory";
import { businessStories } from "../lib/businessStories";

export default function DemoUploadPage() {
  return (
    <PageContainer
      title="Excel Upload"
      description="Generate a valid payroll workbook and push it into the landing bucket as a random finance demo user. The platform handles the rest."
    >
      <UploadCard />
      <BusinessStory {...businessStories.excelUpload} />
    </PageContainer>
  );
}
