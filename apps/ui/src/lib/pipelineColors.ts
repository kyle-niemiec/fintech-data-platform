export type PipelineKind = "excel" | "cdc" | "salesforce" | "curated";

export interface PipelineColor {
  key: PipelineKind;
  label: string;
  solidBg: string;
  solidText: string;
  outlineBorder: string;
  outlineText: string;
  badgeBg: string;
  badgeText: string;
}

export const pipelineColors: Record<PipelineKind, PipelineColor> = {
  excel: {
    key: "excel",
    label: "Excel",
    solidBg: "bg-emerald-600",
    solidText: "text-white",
    outlineBorder: "border-emerald-600",
    outlineText: "text-emerald-700",
    badgeBg: "bg-emerald-50",
    badgeText: "text-emerald-700",
  },
  cdc: {
    key: "cdc",
    label: "CDC",
    solidBg: "bg-blue-600",
    solidText: "text-white",
    outlineBorder: "border-blue-600",
    outlineText: "text-blue-700",
    badgeBg: "bg-blue-50",
    badgeText: "text-blue-700",
  },
  salesforce: {
    key: "salesforce",
    label: "Salesforce",
    solidBg: "bg-purple-600",
    solidText: "text-white",
    outlineBorder: "border-purple-600",
    outlineText: "text-purple-700",
    badgeBg: "bg-purple-50",
    badgeText: "text-purple-700",
  },
  curated: {
    key: "curated",
    label: "Curated",
    solidBg: "bg-amber-500",
    solidText: "text-white",
    outlineBorder: "border-amber-500",
    outlineText: "text-amber-700",
    badgeBg: "bg-amber-50",
    badgeText: "text-amber-700",
  },
};

export const PIPELINE_ORDER: PipelineKind[] = [
  "excel",
  "cdc",
  "salesforce",
  "curated",
];

const EXCEL_NAMES = new Set(["excel_ingestion"]);
const CDC_NAMES = new Set(["cdc_ingestion", "cdc_bronze_write"]);
const SALESFORCE_NAMES = new Set(["salesforce_ingestion"]);
const CURATED_NAMES = new Set(["curated_promotion"]);

export function pipelineKindFor(pipelineName: string): PipelineKind | null {
  if (EXCEL_NAMES.has(pipelineName)) return "excel";
  if (CDC_NAMES.has(pipelineName)) return "cdc";
  if (SALESFORCE_NAMES.has(pipelineName)) return "salesforce";
  if (CURATED_NAMES.has(pipelineName)) return "curated";
  return null;
}

export function pipelineNamesFor(kinds: PipelineKind[]): string[] {
  const names: string[] = [];
  for (const k of kinds) {
    if (k === "excel") names.push(...EXCEL_NAMES);
    if (k === "cdc") names.push(...CDC_NAMES);
    if (k === "salesforce") names.push(...SALESFORCE_NAMES);
    if (k === "curated") names.push(...CURATED_NAMES);
  }
  return names;
}

export function pipelineDisplayNameFor(pipelineName: string): string {
  const kind = pipelineKindFor(pipelineName);
  return kind === "curated" ? "curated" : pipelineName;
}
