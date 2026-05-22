import { Link } from "react-router-dom";
import PageContainer from "../components/layout/PageContainer";

export default function NotFoundPage() {
  return (
    <PageContainer title="Not found" description="This page doesn't exist.">
      <Link to="/" className="btn-primary">
        Back to overview
      </Link>
    </PageContainer>
  );
}
