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

export interface DemoUploadResponse {
  run_trigger_ref: string;
  object_key: string;
  bucket: string;
  demo_user: string;
  rows: number;
  size_bytes: number;
  generated_at: string;
}
