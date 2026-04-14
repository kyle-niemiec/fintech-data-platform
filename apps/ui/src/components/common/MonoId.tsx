import { useState } from "react";
import { shortId } from "../../lib/formatters";

interface Props {
  value: string;
  short?: boolean;
  className?: string;
}

export default function MonoId({ value, short, className }: Props) {
  const [copied, setCopied] = useState(false);
  const display = short ? shortId(value, 10) : value;
  return (
    <button
      type="button"
      title={value}
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1200);
        });
      }}
      className={`inline-flex items-center gap-1 font-mono text-xs text-navy-700 hover:text-navy-900 ${className ?? ""}`}
    >
      <span>{display}</span>
      <span className="text-slate-400">{copied ? "✓" : "⧉"}</span>
    </button>
  );
}
