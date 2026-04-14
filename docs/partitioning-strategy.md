# Partitioning Strategy

This document defines the canonical partitioning plan across all three event-storage layers:

1. Redpanda topic partitions
2. Event-store database partitions
3. MinIO object-path partitions

The goal is to preserve replayability, traceability, and predictable query performance.

## Layer 1: Redpanda Topic Partitioning

### Partitioning Rules

- Partitioning key is chosen by event domain, not by producer service.
- Ordering guarantees are required within each logical execution stream.
- Replay identity is always `(topic, partition, offset)` and is persisted in the event store.

### Keying Strategy

| Topic family | Partition key | Why |
| --- | --- | --- |
| Excel + Salesforce ingestion events (`ingest.*`) | `run_id` | Keeps all events for one run ordered in one partition |
| Orchestration stage events (`pipeline.*`) | `run_id` | Preserves deterministic stage sequencing per run |
| CDC raw + assessed (`cdc.*`) | `<source_table>:<business_key>` | Preserves per-entity order and enables parallelism |
| UI alert events (`ui.alert.*`) | `run_id` | Keeps alert chronology aligned to run timelines |

### Local Partition Counts (Default)

| Topic family | Default partitions | Notes |
| --- | --- | --- |
| `ingest.*` | 6 | Balanced for local fan-out and run-level ordering |
| `pipeline.*` | 6 | Keeps curated stage processing parallel without losing per-run order |
| `cdc.*` | 12 | Higher cardinality for CDC streams and fraud processing |
| `ui.alert.*` | 3 | Lower volume, timeline-oriented consumer use |

If topic throughput exceeds local assumptions, increase partition count and document re-key impact.
Terraform `identity` applies these partition counts when creating topics.

### Retention Baseline

- Raw/assessed CDC topics: long retention for replay and forensic reconstruction.
- Ingestion and stage topics: retention sized to backfill windows plus audit requirements.
- Alert topics: shorter retention allowed if mirrored into event-store tables.

## Layer 2: Event-Store DB Partitioning

### Canonical Partitioned Tables

- `event_store.event_log`: range partitioned by `occurred_at` (monthly partitions).
- `event_store.alert_event`: range partitioned by `occurred_at` (monthly partitions).

Other event-store tables remain unpartitioned initially unless row volume justifies partitioning:
- `pipeline_run`
- `file_ingress`
- `cdc_checkpoint`
- `sf_pull`

### Partition Naming

- pg_partman-managed monthly child names (for example `event_log_pYYYY_MM` and `alert_event_pYYYY_MM`).

### Required Indexes Per `event_log` Partition

- Unique: `(topic, partition, kafka_offset)`
- B-tree: `(run_id, occurred_at)`
- B-tree: `(trace_id, occurred_at)`
- B-tree: `(event_type, occurred_at)`

### Retention and Archive Policy

- Keep recent partitions online for active operations and replay.
- Archive old partitions to cold storage before detach/drop.
- Retention windows are policy-driven and must not violate audit requirements.
- Event-store migrations configure `pg_partman` parent registration for both partitioned tables and enforce per-partition indexes via template tables.
- `pg_cron` runs `SELECT event_store.run_partman_maintenance();` hourly to pre-create monthly partitions.
- `partman.part_config.premake=2` defines the active forward horizon.

## Layer 3: MinIO Object-Path Partitioning

Object paths are partitioned for selective reads, replay windows, and layer-specific access policies.

### Path Templates

#### Landing and Raw

- `landing/source=excel/year=YYYY/month=MM/day=DD/run_id=<run_id>/<original_file>`
- `raw/source=excel/year=YYYY/month=MM/day=DD/run_id=<run_id>/<file>.json|csv`
- `raw/source=salesforce/object=<object>/year=YYYY/month=MM/day=DD/run_id=<run_id>/response.json`

#### Quarantine

- `quarantine/source=<source>/year=YYYY/month=MM/day=DD/run_id=<run_id>/<artifact>`

#### Bronze

- `bronze/source=cdc/table=<table>/year=YYYY/month=MM/day=DD/hour=HH/run_id=<run_id>/part-*.parquet`
- `bronze/source=excel/year=YYYY/month=MM/day=DD/run_id=<run_id>/part-*.parquet`
- `bronze/source=salesforce/object=<object>/year=YYYY/month=MM/day=DD/run_id=<run_id>/part-*.parquet`

#### Silver and Gold

- `silver/domain=<domain>/year=YYYY/month=MM/day=DD/run_id=<run_id>/part-*.parquet`
- `gold/metric=<metric>/year=YYYY/month=MM/day=DD/run_id=<run_id>/part-*.parquet`

Terraform MinIO IAM policies enforce these partitioned path shapes for active writer identities.

### Traceability Metadata Requirements

Each written artifact must keep provenance metadata either in file metadata columns or companion manifests:

- `run_id`
- `trace_id`
- `source_system`
- `event_id` (or event batch id)
- `topic`, `partition`, `offset` (for broker-derived artifacts)
- `lsn_start`, `lsn_end` for CDC-derived batches

### Replay and Backfill Implications

- Topic replay uses `(topic, partition, offset)` checkpoints.
- Event-store replay queries are constrained by partitioned `occurred_at` windows.
- Object replay scans are constrained by partitioned prefixes (`source`, date, run_id).
- Corrections append new partitions/files; no history rewrite.
