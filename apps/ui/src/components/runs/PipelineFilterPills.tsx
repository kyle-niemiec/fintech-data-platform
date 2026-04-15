import {
  PIPELINE_ORDER,
  pipelineColors,
  type PipelineKind,
} from "../../lib/pipelineColors";

interface Props {
  selected: PipelineKind[];
  onToggle: (kind: PipelineKind) => void;
}

export default function PipelineFilterPills({ selected, onToggle }: Props) {
  const selectedSet = new Set(selected);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {PIPELINE_ORDER.map((kind) => {
        const c = pipelineColors[kind];
        const isSelected = selectedSet.has(kind);
        const classes = isSelected
          ? `${c.solidBg} ${c.solidText} border-transparent`
          : `bg-white ${c.outlineText} ${c.outlineBorder} hover:bg-slate-50`;
        return (
          <button
            key={kind}
            type="button"
            aria-pressed={isSelected}
            onClick={() => onToggle(kind)}
            className={`rounded-full border px-4 py-1 text-xs font-semibold uppercase tracking-wide transition-colors ${classes}`}
          >
            {c.label}
          </button>
        );
      })}
      {selected.length > 0 && (
        <span className="text-xs text-navy-500">
          {selected.length} filter{selected.length === 1 ? "" : "s"} active
        </span>
      )}
    </div>
  );
}
