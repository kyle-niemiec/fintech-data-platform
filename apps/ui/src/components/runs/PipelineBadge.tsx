import { pipelineColors, pipelineKindFor } from "../../lib/pipelineColors";

export default function PipelineBadge({ pipelineName }: { pipelineName: string }) {
  const kind = pipelineKindFor(pipelineName);
  if (!kind) {
    return (
      <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-700">
        {pipelineName}
      </span>
    );
  }
  const c = pipelineColors[kind];
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${c.badgeBg} ${c.badgeText}`}
    >
      {c.label}
    </span>
  );
}
