export type RunStatus =
  | "running"
  | "completed"
  | "failed"
  | "scan_failed"
  | "quarantined"
  | string;

export const TERMINAL_STATUSES: ReadonlySet<string> = new Set([
  "completed",
  "failed",
  "scan_failed",
  "quarantined",
]);

export interface RunSummary {
  run_id: string;
  pipeline_class: string;
  pipeline_name: string;
  source_system: string;
  status: RunStatus;
  latest_stage: string | null;
  started_at: string;
  completed_at: string | null;
  is_backfill: boolean;
}

export interface RunDetail extends RunSummary {
  trigger_type: string;
  trigger_event_ref: string;
  initiator: string | null;
  parent_run_id: string | null;
}

export interface RunEventItem {
  occurred_at: string;
  event_type: string;
  source: string;
  run_id: string;
  trace_id: string | null;
  message: string | null;
}

export interface LineageTrailItem {
  event_id: string;
  occurred_at: string;
  stage: string | null;
  input_uris: string[];
  output_uris: string[];
  transform_id: string | null;
  transform_version: string | null;
  event_type: string;
}

export interface ArtifactTrailItem {
  event_id: string;
  occurred_at: string;
  stage: string | null;
  artifact_role: "input" | "output";
  format: string | null;
  uri: string;
  event_type: string;
}

export interface RecentTransactionItem {
  transaction_id: string;
  account_id: string;
  instrument: string;
  amount: string;
  executed_at: string;
  risk_score: string | null;
  risk_flags: string[] | null;
}

export interface DemoUploadResponse {
  run_trigger_ref: string;
  object_key: string;
  bucket: string;
  demo_user: string;
  rows: number;
  size_bytes: number;
  generated_at: string;
  schema_contract_id: string;
  valid: boolean;
}

export interface CdcTransactionRequest {
  high_risk: boolean;
}

export interface CdcTransactionResponse {
  transaction_id: string;
  account_id: string;
  instrument: string;
  amount: string;
  executed_at: string;
  high_risk: boolean;
}

export interface ExcelBackfillRequest {
  target_date: string;
  rows?: number;
  dataset?: "payroll" | "commission_adjustment";
}

export interface ExcelBackfillResponse {
  run_trigger_ref: string;
  object_key: string;
  bucket: string;
  demo_user: string;
  rows: number;
  size_bytes: number;
  target_date: string;
  dataset: string;
  generated_at: string;
}

export interface CdcBackfillRequest {
  target_date: string;
  high_risk?: boolean;
}

export interface CdcBackfillResponse {
  transaction_id: string;
  account_id: string;
  instrument: string;
  amount: string;
  executed_at: string;
  high_risk: boolean;
  target_date: string;
}

export interface ConsumerLagItem {
  group: string;
  topic: string;
  partition: number;
  current_offset: number;
  log_end_offset: number;
  lag: number;
}

export interface PipelineAnalyticsItem {
  pipeline_name: string;
  completed: number;
  failed: number;
  quarantined: number;
  scan_failed: number;
  avg_duration_seconds: number | null;
  alerts_high: number;
  alerts_medium: number;
}

export type AlertSeverity = "high" | "medium" | "low" | string;

export interface AlertItem {
  alert_id: string;
  run_id: string;
  severity: AlertSeverity;
  category: string;
  summary: string;
  details: Record<string, unknown>;
  occurred_at: string;
}
