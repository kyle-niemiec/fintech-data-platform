# Event Contracts

Redpanda is the canonical event backbone for source ingestion, orchestration, audit, and notifications.

## Envelope Standard

Every event must conform to the required envelope:

```json
{
  "event_id": "uuid",
  "event_type": "string",
  "source": "excel|cdc|salesforce|orchestration|notification",
  "run_id": "uuid",
  "pipeline_class": "ingestion|curated",
  "pipeline_name": "excel_ingestion|cdc_ingestion|salesforce_ingestion|curated_promotion",
  "parent_run_id": "uuid|null",
  "trigger_event_ref": "string",
  "trace_id": "uuid",
  "occurred_at": "2026-04-11T19:20:30Z",
  "schema_version": "v1",
  "payload_hash": "sha256-...",
  "payload": {}
}
```

## Artifact Payload Standard

For any event that emits file/object artifacts:

- `stage` identifies where in the pipeline the artifact belongs (`raw`, `quarantine`, `bronze`, `silver`, `gold`).
- `input_uris[]` lists upstream artifact dependencies for that event.
- `output_uris[]` lists artifacts produced by that event.
- Contracts use URI arrays consistently across ingestion and curated pipelines.

## Platform Event Metadata Contract

The following payload metadata keys are standardized across the platform:

| Field | Type | Requirement | Notes |
| --- | --- | --- | --- |
| `message` | TEXT | Required for all events | Human-readable event text used by UI timelines and alerts |
| `stage` | TEXT | Required when event represents pipeline stage activity | Allowed values: `raw`, `quarantine`, `bronze`, `silver`, `gold` |
| `format` | TEXT | Required when `output_uris[]` is non-empty and artifact format is known | Example values: `parquet`, `json`, `xlsx` |
| `transform_id` | TEXT | Required for business-transformation events | Stable transformation identifier (for example `normalize_dedupe_mask`) |
| `transform_version` | TEXT | Required when `transform_id` is present | Version of transformation logic used to produce outputs |

Rules:
- `transform_id` and `transform_version` must appear together.
- For non-transformation events, both transform fields should be omitted.

## Topic Taxonomy

Naming convention:
`<domain>.<system>.<signal>.<version>`

Examples:
- `ingest.excel.uploaded.v1`
- `ingest.excel.scanned.pass.v1`
- `ingest.excel.scanned.fail.v1`
- `ingest.excel.raw.ready.v1`
- `ingest.excel.quarantined.v1`
- `ingest.excel.bronze.ready.v1`
- `cdc.oltp.raw.v1`
- `cdc.oltp.assessed.v1`
- `cdc.oltp.bronze.ready.v1`
- `ingest.sf.pull.started.v1`
- `ingest.sf.pull.succeeded.v1`
- `ingest.sf.pull.failed.v1`
- `ingest.sf.bronze.ready.v1`
- `pipeline.silver.completed.v1`
- `pipeline.silver.failed.v1`
- `pipeline.gold.completed.v1`
- `pipeline.gold.failed.v1`
- `ui.alert.raised.v1`

## Domain Contracts

### Excel

Required payload fields by stage:
- uploaded: `bucket`, `object_key`, `uploader_principal`, `content_type`, `size_bytes`
- scanned: `scan_engine`, `scan_version`, `scan_result`, `failure_reason`
- raw_ready: `stage`, `input_uris[]`, `output_uris[]`, `row_count`, `schema_contract_id`
- quarantined: `stage`, `input_uris[]`, `output_uris[]`, `errors[]`
- bronze_ready: `stage`, `input_uris[]`, `output_uris[]`, `record_count`, `parquet_schema_fingerprint`

### CDC

Required payload fields:
- raw: `topic`, `partition`, `offset`, `lsn`, `op`, `before`, `after`, `source_ts_ms`
- assessed: `risk_score`, `risk_flags[]`, `fraud_rule_version`, `original_topic_metadata`
- bronze_ready: `stage`, `input_uris[]`, `output_uris[]`, `record_count`, `first_lsn`, `last_lsn`

### Salesforce

Required payload fields:
- pull_started: `object_name`, `cursor_from`, `cursor_to`, `request_id`
- pull_succeeded: `stage`, `input_uris[]`, `output_uris[]`, `request_id`, `response_checksum`, `records_returned`
- pull_failed: `request_id`, `error_code`, `error_message`, `retry_attempt`
- bronze_ready: `stage`, `input_uris[]`, `output_uris[]`, `object_name`, `record_count`

### Orchestration and Alerts

Required payload fields:
- stage_completed: `stage`, `input_uris[]`, `output_uris[]`, `duration_ms`
- stage_failed: `stage`, `error_code`, `error_message`, `retryable`
- ui_alert_raised: `severity`, `category`, `message`, `run_url`

Transformation provenance:
- For events that perform business transformation, include `transform_id` and `transform_version`.
- This enables replay fidelity and audit traceability of which transformation logic produced each output artifact set.

## Ordering and Idempotency

- Ordering key defaults to `run_id`, except CDC where ordering key is `(source_table, partition, lsn)`.
- Consumers must support at-least-once delivery.
- `event_id` is the dedupe key in event-store write paths.
- Replays must preserve original event payload and metadata.

## Topic Partitioning Plan

| Topic family | Partition key | Default partitions (local) |
| --- | --- | --- |
| `ingest.*` | `run_id` | 6 |
| `pipeline.*` | `run_id` | 6 |
| `cdc.*` | `<source_table>:<business_key>` | 12 |
| `ui.alert.*` | `run_id` | 3 |

Rules:
- Ordering is guaranteed only within a partition.
- Producer payloads must include fields needed to reconstruct order (`run_id`, and for CDC `lsn`).
- Consumers persist `(topic, partition, offset)` in the event store for replay checkpoints (`offset` is stored in `event_log.kafka_offset`).
- Event-first invariant: a trigger event creates the run context; runs do not pre-exist their initiating event.
- Terraform `identity` provisions the canonical topic set with these partition defaults and applies service-identity ACLs.

## Run Boundary Rules

- The three ingestion pipelines are independent:
  - `excel_ingestion`
  - `cdc_ingestion`
  - `salesforce_ingestion`
- Curated promotion is a separate pipeline (`curated_promotion`) that begins only after `*.bronze.ready.v1`.
- Curated runs may link back to the upstream ingestion run via `parent_run_id`, but execution policies remain separate.
- Pipeline domain mapping is fixed:
  - `excel_ingestion` events use `source=excel` and `pipeline_class=ingestion`
  - `cdc_ingestion` events use `source=cdc` and `pipeline_class=ingestion`
  - `salesforce_ingestion` events use `source=salesforce` and `pipeline_class=ingestion`
  - `curated_promotion` events use `source=orchestration` and `pipeline_class=curated`

## Versioning Rules

- Breaking payload changes require new topic version suffix.
- Additive changes remain same version if old consumers can ignore new fields.
- Schema registry entry must exist for each active version.

## Retention and Replay

- Topics retain enough history for backfill and forensic replay windows.
- Event store checkpoints track replay positions per consumer group.
- Replay jobs append new correction events; no mutation of prior events.
