# Architecture

## Intent

This platform is designed as an event-driven data system where pipeline execution is independent from the backend API.

- Source systems and storage events drive ETL.
- Redpanda (Kafka API-compatible) is the backbone for orchestration and replay.
- Airflow executes DAGs based on events and schedules.
- FastAPI is a read-only query boundary for the UI.
- UI access is anonymous in demo mode; no human login is required.

## System Topology

```text
+----------------+      +-------------------------------+
| Source Systems | ---> | Ingress + Validation Services |
+----------------+      +-------------------------------+
     | Excel upload           | ClamAV + file gate checks
     | OLTP CDC               | MinIO event notifier
     | Salesforce pull        | Debezium connectors
     v                        v
                +---------------------------+
                | Redpanda Event Backbone   |
                | (durable topic contracts) |
                +---------------------------+
                              |
                              v
                +---------------------------+
                | Airflow DAG Orchestration |
                | raw/quarantine -> bronze  |
                | bronze -> silver -> gold  |
                +---------------------------+
                              |
                              v
                +---------------------------+
                | MinIO Lakehouse Storage   |
                | landing/raw/quarantine    |
                | bronze/silver/gold        |
                +---------------------------+
                              |
                              v
                +---------------------------+
                | Trino + Iceberg           |
                +---------------------------+

+----------------------+        +--------------------------+
| Event Store Database | <----> | FastAPI UI Query API     |
| (append-only audit)  |        | (read-only endpoints)    |
+----------------------+        +--------------------------+
                                      |
                                      v
                                  UI Dashboard
```

## Control Boundaries

### Data Plane

The data plane owns:
- Source ingestion.
- Validation, quarantine, transformation.
- Bronze/silver/gold movement.
- Event publication and replay.
- Audit event persistence.

Pipeline domains in the data plane:
- Ingestion domain (independent runs): Excel, CDC, Salesforce.
- Curated domain (independent runs): bronze -> silver -> gold promotion.

Boundary rule:
- Ingestion pipelines end at bronze readiness.
- Curated pipeline begins at bronze-ready events and follows its own orchestration behavior.

Primary runtime components:
- MinIO
- Redpanda
- Airflow
- ClamAV scanner
- Excel validation trigger worker
- Excel bronze writer

Planned for later phases:
- Debezium
- Fraud worker
- Salesforce extractor
- Curated promotion workers/DAGs

### Query Plane

The query plane owns:
- UI-oriented read models.
- Aggregated run status views.
- Artifact and lineage trace views.
- Alert feed retrieval.

FastAPI in this repo belongs to the query plane only.

## Event-Driven Orchestration Pattern

### EventBridge Equivalent (Local)

Local event routing standard:
- MinIO notifications publish to Redpanda topics.
- Debezium publishes CDC envelopes to Redpanda topics.
- Airflow consumes trigger topics and publishes stage-completion events.

This pattern gives:
- Decoupled producers and consumers.
- Durable replay for recovery/backfill.
- Auditable orchestration history.

### Partitioning Across Storage Layers

Partitioning is required in three places:
- Redpanda topics: keyed for per-run ordering and CDC entity ordering.
- Event-store database: monthly range partitions on event time.
- MinIO lakehouse paths: source/date/run_id partitioned prefixes.
- Enforcement is IaC-owned: Terraform provisions topic partition counts and MinIO path-constrained writer policies, while event-store SQL migrations configure pg_partman + pg_cron for monthly partition automation.

See [partitioning-strategy.md](partitioning-strategy.md) for the canonical plan and defaults.

## Pipeline Flow Summary

### Excel
1. Finance uploads to `landing/` using constrained write identity.
2. MinIO emits object-created event to Redpanda.
3. Scan worker runs ClamAV + type/size checks and emits verdict events.
4. Trigger worker consumes `scanned.pass` and creates idempotent Airflow DAG runs.
5. Airflow validates schema/content and writes either `raw/` or `quarantine/`.
6. Bronze writer consumes `raw.ready`, writes Parquet to `bronze/`, and emits bronze-ready events.

### CDC
1. OLTP changes are captured by Debezium.
2. Raw CDC envelopes are written to Kafka topics.
3. Fraud worker consumes CDC events, scores risk, flags OLTP records, emits assessed events.
4. Bronze writer persists assessed payloads with Kafka metadata + LSN, with no business transformation.

### Salesforce
1. Airflow runs scheduled incremental pulls using last cursor.
2. Raw API envelopes are persisted and linked to pull events.
3. Airflow writes Parquet outputs to bronze and emits completion events.

### Curated Layers
1. Bronze-ready event triggers normalization DAG.
2. Silver transformations apply dedupe, masking, SCD2 rules.
3. Gold DAG produces KPI aggregates with no direct PII.
4. Stage events are published for UI observability and replay.

## Network Model

- Processing components run on internal Docker networks.
- Only explicit ingress surfaces are exposed publicly (UI/API/admin consoles when needed).
- ETL workers do not require public inbound access.

## Immutability and Replay

- Event contracts are append-only and versioned.
- Bronze is source-faithful and replayable.
- Corrections append new events rather than mutating history.
- Backfills run via replay from event topics and event-store checkpoints.

## IaC Ownership Model

- Docker Compose: runtime service topology and network isolation.
- Terraform: identities, ACLs, bucket policies, encryption policy, service credentials.
- SQL migrations: event store schema and append-only constraints.
- Airflow DAG definitions: orchestrated transformation contract.
- Topic schema definitions: event interface contract.
