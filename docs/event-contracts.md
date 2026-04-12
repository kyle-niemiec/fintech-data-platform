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
  "trace_id": "uuid",
  "occurred_at": "2026-04-11T19:20:30Z",
  "schema_version": "v1",
  "payload_hash": "sha256-...",
  "payload": {}
}
```

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
- raw_ready: `raw_uri`, `row_count`, `schema_contract_id`
- quarantined: `quarantine_uri`, `errors[]`
- bronze_ready: `bronze_uri`, `record_count`, `parquet_schema_fingerprint`

### CDC

Required payload fields:
- raw: `topic`, `partition`, `offset`, `lsn`, `op`, `before`, `after`, `source_ts_ms`
- assessed: `risk_score`, `risk_flags[]`, `fraud_rule_version`, `original_topic_metadata`
- bronze_ready: `bronze_uri`, `record_count`, `first_lsn`, `last_lsn`

### Salesforce

Required payload fields:
- pull_started: `object_name`, `cursor_from`, `cursor_to`, `request_id`
- pull_succeeded: `request_id`, `response_uri`, `response_checksum`, `records_returned`
- pull_failed: `request_id`, `error_code`, `error_message`, `retry_attempt`
- bronze_ready: `bronze_uri`, `object_name`, `record_count`

### Orchestration and Alerts

Required payload fields:
- stage_completed: `stage`, `input_uris[]`, `output_uris[]`, `duration_ms`
- stage_failed: `stage`, `error_code`, `error_message`, `retryable`
- ui_alert_raised: `severity`, `category`, `summary`, `run_url`

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
- Consumers persist `(topic, partition, offset)` in the event store for replay checkpoints.

## Versioning Rules

- Breaking payload changes require new topic version suffix.
- Additive changes remain same version if old consumers can ignore new fields.
- Schema registry entry must exist for each active version.

## Retention and Replay

- Topics retain enough history for backfill and forensic replay windows.
- Event store checkpoints track replay positions per consumer group.
- Replay jobs append new correction events; no mutation of prior events.
