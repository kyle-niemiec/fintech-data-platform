# Operations

This runbook defines the local event-driven operating sequence.

## Prerequisites

- Docker + Docker Compose
- Python 3.12+
- GNU Make
- `jq` (optional)

Terraform CLI is run inside a Docker image via Make targets; no host Terraform installation is required.

## Environment Configuration

1. Copy environment template:

```bash
cp infra/.env.example infra/.env
```

2. Set required secrets and credentials for:
   - Postgres and event-store DB users
   - MinIO root and service users
   - Redpanda client credentials
   - Keycloak demo-service client and demo persona seed password
   - KES/Vault key provider settings
   - Airflow and connector service credentials

Host loopback endpoints are not required for Terraform. Terraform uses Docker-internal service DNS (`postgres`, `event_store_db`, `minio`, `keycloak`).

## Startup Sequence (Target Local Stack)

1. Initialize Terraform providers:

```bash
make infra-tf-init
```

2. Start core stateful services (Postgres, event-store DB, MinIO, Redpanda):

```bash
docker compose -f infra/docker-compose.yaml --env-file infra/.env up -d postgres minio redpanda event_store_db
```

3. Apply Terraform bootstrap (bucket/policies, topic ACLs, identities, encryption policies):

```bash
make infra-tf-bootstrap
```

4. Start identity and orchestration services:

```bash
docker compose -f infra/docker-compose.yaml --env-file infra/.env up -d keycloak airflow-webserver airflow-scheduler airflow-worker
```

5. Start ingestion and processing services:

```bash
docker compose -f infra/docker-compose.yaml --env-file infra/.env up -d clamav scanner debezium fraud-worker sf-extractor bronze-writer curated-promoter
```

6. Apply Terraform identity and access layer:

```bash
make infra-tf-apply
```

7. Start UI query API and UI frontend:

```bash
make api-install
make api-dev
```

## Internal Service Access (No Data-Plane Host Ports)

- Postgres/event-store/MinIO/Redpanda are intentionally not published to host ports.
- Use container-exec paths for local diagnostics:

```bash
make db-psql-core
make db-psql-event-store
docker compose -f infra/docker-compose.yaml --env-file infra/.env exec minio sh
docker compose -f infra/docker-compose.yaml --env-file infra/.env exec redpanda rpk cluster info
```

## Source-to-Gold Validation Sequence

### Excel validation path

1. Upload workbook to landing prefix using finance upload identity.
2. Confirm events in order:
   - `ingest.excel.uploaded.v1`
   - `ingest.excel.scanned.*.v1`
   - `ingest.excel.raw.ready.v1` or `ingest.excel.quarantined.v1`
   - `ingest.excel.bronze.ready.v1`
3. Confirm event-store run timeline includes every stage.
4. Confirm run metadata indicates `pipeline_class=ingestion` and `pipeline_name=excel_ingestion`.

### CDC validation path

1. Wait for internal CDC data generator cycle (5-10 minutes) or insert/update OLTP transaction rows for an immediate check.
2. Confirm CDC events and fraud-assessed events are emitted.
3. Verify bronze records include Kafka metadata and LSN.
4. Confirm run metadata indicates `pipeline_class=ingestion` and `pipeline_name=cdc_ingestion`.

### Salesforce validation path

1. Wait for scheduled incremental pull trigger.
2. Confirm pull started/succeeded or failed events.
3. Verify raw response persistence and bronze output event.
4. Confirm run metadata indicates `pipeline_class=ingestion` and `pipeline_name=salesforce_ingestion`.

### Curated validation path

1. Confirm bronze-ready events trigger silver DAG.
2. Confirm silver-completed events trigger gold DAG.
3. Verify UI run trace shows full lineage through gold.
4. Confirm curated promotion runs are tracked separately with `pipeline_class=curated` and linked to ingestion runs via `parent_run_id`.

## Replay and Backfill

- Replay from Redpanda offsets using consumer-group checkpoints.
- Replay jobs append correction events; history remains immutable.
- For file-based sources, reprocess by emitting new replay trigger events tied to original run lineage.

## Partitioning Operations

- Create monthly event-store partitions ahead of time for `event_log` and `alert_event`.
- Validate topic partition counts and keys against [event-contracts.md](event-contracts.md) before deploying producers.
- Validate object path partition templates from [partitioning-strategy.md](partitioning-strategy.md) in writer jobs.
- Confirm replay jobs honor `(topic, partition, offset)` checkpoints and CDC LSN windows.

## Failure Handling

- Scan failures route to quarantine and emit alert events.
- Validation failures route to quarantine with structured error payload.
- Airflow retries follow DAG policy and emit retry metadata events.
- Fraud high-risk outcomes emit UI alerts and flag OLTP records.

## Operational Constraints

- ETL must keep running if FastAPI is down.
- Processing services remain on internal networks only.
- No in-place mutation of event history for corrections.
- Encrypted object-write policy is required for curated layers.
- Runs are event-initiated only; a `pipeline_run` must not exist before its trigger event.
- `pipeline_run` domain mapping is enforced (`pipeline_class`, `pipeline_name`, `source_system`, `parent_run_id` must match the fixed pipeline contract).

## Observability Essentials

- Redpanda topic lag and consumer-group health.
- Airflow DAG success/failure and retry rates.
- Event-store append throughput and read-model freshness.
- Quarantine volume and top failure reasons.
