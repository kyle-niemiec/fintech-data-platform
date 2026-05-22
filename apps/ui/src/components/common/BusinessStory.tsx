import type { ReactNode } from "react";
import MeridianMark from "./MeridianMark";

// A branded, onboarding-style callout that explains the business purpose of a
// page. Rendered as the last element on each page, above the app footer.
export default function BusinessStory({
  title,
  body,
}: {
  title: string;
  body: ReactNode;
}) {
  return (
    <aside className="card card-pad border-l-4 border-navy-700 bg-navy-50/40">
      <div className="flex gap-4">
        <MeridianMark size={36} className="mt-0.5 shrink-0 rounded-md shadow-sm" />
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-navy-500">
            From the Meridian playbook
          </p>
          <h2 className="mt-0.5 text-base font-semibold text-navy-900">{title}</h2>
          <div className="mt-2 space-y-2 text-sm leading-relaxed text-navy-700">
            {body}
          </div>
        </div>
      </div>
    </aside>
  );
}
