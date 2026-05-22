# Operations

This runbook defines the local event-driven operating sequence.

## Prerequisites

- Docker + Docker Compose
- GNU Make
- `jq` (optional)

Terraform CLI is run inside a Docker image via Make targets; no host Terraform installation is required.
The event-store service uses a custom Postgres image that installs `pg_partman` and `pg_cron` during build.

## Environment Configuration

1. Copy environment template:

```bash
cp infra/.env.example infra/.env
```

2. Set required secrets and credentials for:
   - Postgres and event-store DB users
   - Vault/KES bootstrap and KMS identity values
   - MinIO root and service users
   - Redpanda client credentials
   - Keycloak demo-service client and demo persona seed password
   - Airflow and connector service credentials

Host loopback endpoints are not required for Terraform. Terraform uses Docker-internal service DNS (`postgres`, `event_store_db`, `minio`, `keycloak`).

If you need new KES client credentials, generate them before startup:

```bash
docker run --rm minio/kes:latest identity new
```

## Startup Sequence (Target Local Stack)

Use this Compose file stack for direct `docker compose` commands:

```bash
COMPOSE_FILES="-f infra/docker-compose.yaml -f infra/compose/foundation.yaml -f infra/compose/orchestration.yaml -f infra/compose/excel-pipeline.yaml -f infra/compose/cdc-pipeline.yaml -f infra/compose/salesforce-pipeline.yaml -f infra/compose/curated-pipeline.yaml -f infra/compose/api.yaml -f infra/compose/ui.yaml"
```

Run the staged infra bootstrap first (single command):

```bash
make infra-up
```

Or run individual steps (1-12):

```bash
make infra-up 1     # terraform init (bootstrap + identity phases)
make infra-up 2     # postgres, event-store, vault, kes, minio, redpanda
make infra-up 3     # terraform bootstrap apply
make infra-up 4     # keycloak
make infra-up 5     # terraform identity apply
make infra-up 6     # excel pipeline (airflow + scanner/trigger/bronze writer)
make infra-up 7     # cdc pipeline (oltp_db, load gen, Debezium, fraud worker, bronze writer)
make infra-up 8     # salesforce pipeline (mock service + bronze writer)
make infra-up 9     # curated pipeline (iceberg-rest, trino, curated init)
make infra-up 10    # read-only UI query API
make infra-up 11    # demo UI
make infra-up 12    # status (docker compose ps)
```

The staged flow includes the read-only UI query API (`make infra-up 10`) and demo UI (`make infra-up 11`).
The API is exposed at `http://localhost:8000` and the UI is exposed at `http://localhost:3000`.

### Development override: MinIO console on host

By default, MinIO remains internal-only. For local development that needs browser access to MinIO (`:9001`), use:

```bash
make infra-up-dev
```

This enables the dev override compose file (`infra/compose/dev/minio-console-access.yaml`) and publishes:
- `http://localhost:9000` (S3 API)
- `http://localhost:9001` (MinIO Console)

## Internal Service Access (Default Stack)

- Postgres/event-store/MinIO/Redpanda are intentionally not published to host ports.
- Vault/KES are also internal-only and not host-published.
- Use container-exec paths for local diagnostics:

```bash
make db-psql-core
make db-psql-event-store
docker compose $COMPOSE_FILES --env-file infra/.env exec minio sh
docker compose $COMPOSE_FILES --env-file infra/.env exec redpanda rpk cluster info
docker compose $COMPOSE_FILES --env-file infra/.env exec vault sh
docker compose $COMPOSE_FILES --env-file infra/.env logs kes --tail=50
```

## KMS Readiness Checks

1. Verify Vault transit key exists:

```bash
docker compose $COMPOSE_FILES --env-file infra/.env exec -T vault sh -ec 'export VAULT_ADDR=http://127.0.0.1:8200; export VAULT_TOKEN="$VAULT_DEV_ROOT_TOKEN_ID"; vault read transit/keys/fintech-minio-kms-root'
```

2. Verify KES started against Vault:

```bash
docker compose $COMPOSE_FILES --env-file infra/.env logs kes --tail=50
```

3. Verify MinIO is up with KES endpoint configured:

```bash
docker compose $COMPOSE_FILES --env-file infra/.env logs minio --tail=50
```

4. Vault is intentionally running in dev mode for local demonstration. Restarting the `vault` container resets its in-memory state and can make previously written ciphertext undecryptable. Treat Vault restarts as a local re-bootstrap event.

## Event-Store Hardening Migration Note

`infra/db/event-store-migrations/02_harden_privileges.sql` applies automatically on fresh DB initialization.
If your `event_store_db` volume predates this migration, either:

1. Run `make infra-clean` and re-run startup steps, or
2. Apply the migration manually from inside the container:

```bash
make db-psql-event-store
\i /docker-entrypoint-initdb.d/02_harden_privileges.sql
```

## Excel Validation Sequence (Phase 3)

### Excel validation path

1. Upload workbook to landing prefix using finance upload identity.
2. Confirm scanner + trigger + DAG + writer events in order:
   - `ingest.excel.uploaded.v1`
   - `ingest.excel.scanned.pass.v1` or `ingest.excel.scanned.fail.v1`
   - `ingest.excel.raw.ready.v1` or `ingest.excel.quarantined.v1`
   - `ingest.excel.bronze.ready.v1`
3. Confirm `excel_validation_trigger` creates exactly one DAG run per run ID (`excel_validation__<run_id>`; duplicate trigger should return 409-idempotent success).
4. Confirm event-store run timeline includes every stage.
5. Confirm run metadata indicates `pipeline_class=ingestion` and `pipeline_name=excel_ingestion`.

### Negative-path checks

1. Virus fail path:
   - publish/upload known-infected sample (EICAR test file in xlsx container)
   - confirm `ingest.excel.scanned.fail.v1`
   - confirm run closes `scan_failed`
2. Schema fail path:
   - upload structurally invalid workbook
   - confirm `ingest.excel.quarantined.v1`
   - confirm run closes `quarantined`

## CDC + Fraud Validation Sequence (Phase 4)

### Bring-up

```bash
make infra-up            # full local stack (staged steps 1-12; CDC pipeline is step 7)
# or bring up just the CDC pipeline against an already-running base:
make infra-cdc-pipeline  # oltp_db, load gen, Debezium, fraud worker, bronze writer
```

The OLTP load generator runs continuously with randomized cadence
(`OLTP_LOAD_GEN_INTERVAL_MIN_SECONDS`..`OLTP_LOAD_GEN_INTERVAL_MAX_SECONDS`,
30-60s by default) so no manual data writes are required.

### Happy-path validation

1. Wait for Debezium snapshot completion. Tail the connector log:

   ```bash
   docker logs -f fintech_debezium_server | grep -i "Snapshot ended"
   ```

2. Confirm raw CDC envelopes on the canonical topic:

   ```bash
   docker exec fintech_redpanda rpk topic consume cdc.oltp.raw.v1 -n 5
   ```

3. Trigger a deterministic fraud path by inserting an AAPL trade above its calibrated threshold (10,000):

   ```bash
   make db-psql-oltp
   \c fintech_oltp
   INSERT INTO trading.transaction (account_id, instrument, amount, executed_at)
   VALUES (gen_random_uuid(), 'AAPL', 15000, now());
   ```

4. Within seconds the assessed topic should carry `risk_flags` including `risk_threshold_exceeded` (and the instrument-specific threshold flag):

   ```bash
   docker exec fintech_redpanda rpk topic consume cdc.oltp.assessed.v1 -n 1
   ```

5. Confirm the idempotent `risk_flag` row is persisted:

   ```sql
   SELECT transaction_id, risk_score, risk_flags
   FROM trading.risk_flag ORDER BY flagged_at DESC LIMIT 3;
   ```

6. After the bronze batch flush window, inspect MinIO and the checkpoint table:

   ```bash
   docker exec fintech_minio mc ls --recursive local/fintech-lakehouse/bronze/source=cdc/ | head
   ```

   ```sql
   SELECT run_id, source_table, lsn_start, lsn_end, record_count
   FROM event_store.cdc_checkpoint ORDER BY recorded_at DESC LIMIT 5;
   ```

7. Three-event arc per batch is visible in the event log:

   ```sql
   SELECT event_type, count(*) FROM event_store.event_log
   WHERE event_type LIKE 'cdc.%' GROUP BY 1;
   ```

### Replay test

```bash
docker compose stop cdc_bronze_writer
docker exec fintech_redpanda rpk group seek cdc-bronze-writer-v1 --to start
docker compose start cdc_bronze_writer
```

Verify no duplicate `trading.risk_flag` rows (idempotency holds) and distinct
`run_id`s on new bronze objects.

### Operational notes

- Replication slot growth: sustained Debezium downtime + active OLTP writes
  grow WAL. Monitor with `SELECT slot_name, active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS backlog FROM pg_replication_slots;`.
- Fraud scoring is versionless in this demo; assessed events and `trading.risk_flag` rows carry no rule-version label.

### Salesforce and curated pipelines

- The Salesforce pull (Phase 5) and curated promotion (Phase 6) pipelines are implemented and are
  brought up by `make infra-up` (steps 8 and 9), or standalone via `make infra-salesforce-pipeline`
  and `make infra-curated-pipeline`.
- Salesforce: a scheduled `salesforce_incremental_pull` Airflow DAG pulls from the mock service,
  persists raw artifacts, and emits `ingest.salesforce.bronze.ready.v1`.
- Curated: `*.bronze.ready.v1` events drive the listener/transform DAG pairs
  (`silver_curated_promotion` -> `gold_curated_aggregation`) into Iceberg via Trino.

## Replay and Backfill

- Replay from Redpanda offsets using consumer-group checkpoints.
- Replay jobs append correction events; history remains immutable.
- For file-based sources, reprocess by emitting new replay trigger events tied to original run lineage.

## Partitioning Operations

- Event-store monthly partitions are managed automatically by `pg_partman` + `pg_cron`.
- Verify event-store partition config and premake horizon:

```bash
make db-psql-event-store
SELECT parent_table, partition_interval, premake, automatic_maintenance FROM partman.part_config ORDER BY parent_table;
```

- Run an on-demand maintenance cycle (operational/debug use only):

```bash
make db-psql-event-store
SELECT event_store.run_partman_maintenance();
```

- Validate topic partition counts and keys against [event-contracts.md](event-contracts.md) before deploying producers.
- Validate object path partition templates from [partitioning-strategy.md](partitioning-strategy.md); MinIO writer policies enforce partitioned path shapes for active service users.
- Confirm replay jobs honor `(topic, partition, offset)` checkpoints and CDC LSN windows.

## Failure Handling

- Scan failures emit `ingest.excel.scanned.fail.v1` and close runs as `scan_failed`.
- Validation failures emit `ingest.excel.quarantined.v1` and close runs as `quarantined`.
- Bronze conversion failures raise `ui.alert.raised.v1` and close runs as `failed`.
- Airflow trigger worker commits Kafka offsets only after DAG trigger success or idempotent 409.

## Recovery Playbooks

Each playbook follows the same structure: **Detect → Diagnose → Recover → Verify**.

### Excel Ingestion

**Scan failure** (`scan_failed` run)
- Detect: `GET /ui/alerts?limit=50` shows `excel_scanner` alert; run status is `scan_failed`.
- Diagnose: `docker logs fintech_excel_scanner --tail=100` for MIME/size/ClamAV error detail.
- Recover: Fix the source file, re-upload via `POST /ui/demo/upload` (or `POST /ui/demo/backfill/excel` for a historical date). Kafka offsets were left uncommitted, so the scanner will retry automatically on container restart if the original message is still in the topic.
- Verify: New run appears; status reaches `completed`; no `scan_failed` alert on the new run.

**Schema quarantine** (`quarantined` run)
- Detect: `GET /ui/alerts` shows `excel_schema_quarantined`; run status is `quarantined`.
- Diagnose: Check artifact at `quarantine/` path in MinIO for the rejected file; validate against the schema contract in `services/libs/event_schemas/`.
- Recover: Correct the workbook schema and re-upload. Each upload creates a new run; the quarantined run is preserved as audit history.
- Verify: New run reaches `completed`; bronze Parquet written to `bronze/source=excel/...`.

**Bronze write failure** (`failed` run)
- Detect: `GET /ui/alerts` shows `excel_bronze_write_failed`; run status is `failed`.
- Diagnose: `docker logs fintech_excel_bronze_writer --tail=100`; check MinIO/event-store connectivity.
- Recover: The bronze writer left Kafka offsets uncommitted. Restart the container after fixing the underlying issue — it will reprocess from the uncommitted offset.
  ```bash
  docker compose $COMPOSE_FILES --env-file infra/.env restart excel_bronze_writer
  ```
- Verify: Existing run closes `completed`; bronze Parquet appears; no new alert.

---

### CDC + Fraud Pipeline

**Debezium not capturing / lag growing**
- Detect: `make consumer-lag` shows growing lag on `cdc.oltp.raw.v1`; `docker logs fintech_debezium_server` shows connector errors.
- Diagnose: Check replication slot backlog:
  ```sql
  SELECT slot_name, active, pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn) AS backlog
  FROM pg_replication_slots;
  ```
- Recover: Restart Debezium. On fresh re-snapshot, the fraud worker's idempotency guard (`(raw_topic, raw_partition, raw_offset)` upsert key on `trading.risk_flag`) prevents duplicate flags.
  ```bash
  docker compose $COMPOSE_FILES --env-file infra/.env restart debezium_server
  ```
- Verify: Lag on `cdc.oltp.raw.v1` trends to zero; new assessed events appear on `cdc.oltp.assessed.v1`.

**Fraud worker failure**
- Detect: `GET /ui/alerts` shows `cdc_fraud_worker_failed` or `cdc_assessed_envelope_build_failed`; Kafka offsets uncommitted.
- Diagnose: `docker logs fintech_fraud_worker --tail=100`.
- Recover: Fix the underlying issue (e.g. event-store connectivity) then restart. Uncommitted offsets cause the worker to reprocess from the last committed position. Idempotency ensures no duplicate flags.
  ```bash
  docker compose $COMPOSE_FILES --env-file infra/.env restart fraud_worker
  ```
- Verify: Runs for pending CDC events reach `completed`; `trading.risk_flag` rows are correct with no duplicates.

**CDC bronze write failure**
- Detect: Alert `cdc_bronze_write_failed`; `cdc_bronze_writer` logs show MinIO or event-store error.
- Recover: Restart after fixing connectivity. Uncommitted offsets replay the batch.
  ```bash
  docker compose $COMPOSE_FILES --env-file infra/.env restart cdc_bronze_writer
  ```
- Full replay from start (e.g. after rule update): `make replay-group GROUP=cdc-bronze-writer-v1` then restart.
- Verify: Bronze Parquet files under `bronze/source=cdc/...` reappear; `cdc_checkpoint` rows are updated.

---

### Salesforce Pipeline

**Pull DAG failure**
- Detect: `GET /ui/alerts` shows `salesforce_pull_failed`; Airflow shows failed `salesforce_incremental_pull` run.
- Diagnose: Check Airflow logs for the failed task; check mock Salesforce service availability.
- Recover: Trigger a fresh DAG run from the Airflow UI (or wait for the next scheduled interval — the cursor checkpoint persists the last successful pull). The pull is incremental; it resumes from `latest_sf_cursor`.
- Verify: New pull run reaches `completed`; `ingest.salesforce.bronze.ready.v1` is emitted; new bronze Parquet appears.

**Salesforce bronze write failure**
- Detect: Alert `salesforce_bronze_write_failed`; run status is `failed`.
- Recover: Kafka offsets left uncommitted; restart the writer after fixing the issue.
  ```bash
  docker compose $COMPOSE_FILES --env-file infra/.env restart salesforce_bronze_writer
  ```
- Verify: Run closes `completed`; Parquet written to `bronze/source=salesforce/...`.

---

### Curated Promotion (Silver / Gold)

**Silver DAG failure**
- Detect: `GET /ui/alerts` shows `curated_promotion_failed` (severity `high`); Airflow shows failed `silver_curated_promotion` run.
- Diagnose: Check Airflow logs for the failed task (usually Trino connectivity or SCD2 merge SQL issue).
- Recover: Re-emit the bronze-ready event for the failed run by re-triggering the source pipeline run (Excel or Salesforce backfill). The curated listener will fan out a new silver transform run. The `(pipeline_name, trigger_event_ref)` idempotency key prevents duplicate runs for the same bronze ref.
- Verify: New silver run reaches `completed`; `event_store.silver_checkpoint` row is recorded; `pipeline.silver.completed.v1` is emitted.

**Gold DAG failure**
- Detect: Alert `curated_promotion_failed` from gold; Airflow `gold_curated_aggregation` run failed.
- Diagnose: Check Airflow task logs for Trino INSERT error.
- Recover: Re-emit `pipeline.silver.completed.v1` from the failed silver run by re-triggering the silver transform. The gold listener will pick it up and open a new gold run.
- Verify: New gold run reaches `completed`; `event_store.gold_checkpoint` row is recorded; Iceberg gold table is updated.

---

## Operational Constraints

- ETL must keep running if FastAPI is down.
- Processing services remain on internal networks only.
- No in-place mutation of event history for corrections.
- Encrypted object-write policy is required for curated layers.
- Runs are event-initiated only; a `pipeline_run` must not exist before its trigger event.
- `pipeline_run` domain mapping is enforced (`pipeline_class`, `pipeline_name`, `source_system`, `parent_run_id` must match the fixed pipeline contract).

## Encryption Enforcement Validation

Use `minio/mc` on the internal network to validate deny/allow behavior:

- Negative test (must fail): write to `bronze/*` without SSE-KMS headers.
- Positive test (must pass): write to `bronze/*` with `--enc-kms ...=<kms-key-id>`.
- Control test (must pass): write to `raw/*` without SSE-KMS headers.

Reference command pattern:

```bash
docker run --rm --env-file infra/.env --entrypoint /bin/sh --network infra_platform_internal minio/mc -ec '
mc alias set transform http://minio:9000 "$MINIO_TRANSFORM_USER" "$MINIO_TRANSFORM_SECRET"
mc cp /tmp/file transform/fintech-lakehouse/bronze/without-headers.txt
mc cp --enc-kms "transform/fintech-lakehouse/bronze/=fintech-lakehouse-kms-key" /tmp/file transform/fintech-lakehouse/bronze/with-headers.txt
'
```

## Rotation Procedures

### Vault Transit Key Rotation

```bash
docker compose $COMPOSE_FILES --env-file infra/.env exec -T vault sh -ec 'export VAULT_ADDR=http://127.0.0.1:8200; export VAULT_TOKEN="$VAULT_DEV_ROOT_TOKEN_ID"; vault write -f transit/keys/fintech-minio-kms-root/rotate; vault read -field=latest_version transit/keys/fintech-minio-kms-root'
```

After rotation, validate one new SSE-KMS write and read back both pre- and post-rotation objects.

### MinIO Service Credential Rotation (Terraform)

1. Update secrets in `infra/.env` for one or more MinIO runtime users.
2. Re-apply bootstrap:

```bash
make infra-tf-bootstrap
```

3. Restart any dependent worker containers using the rotated credentials.
4. Validate expected writes/reads for those principals.
5. `terraform plan` may continue to show `minio_iam_user.* secret` updates because MinIO does not return cleartext secrets to the provider.
Treat runtime auth validation as the acceptance check for secret rotation.
6. If a rotated principal still fails authentication, re-assert the secret with MinIO admin and retest:

```bash
docker run --rm --env-file infra/.env --entrypoint /bin/sh --network infra_platform_internal minio/mc -ec '
mc alias set root http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc admin user add root "$MINIO_INGEST_USER" "$MINIO_INGEST_SECRET"
mc admin user add root "$MINIO_VALIDATION_USER" "$MINIO_VALIDATION_SECRET"
mc admin user add root "$MINIO_TRANSFORM_USER" "$MINIO_TRANSFORM_SECRET"
'
```

### Event-Store Runtime Password Rotation (Terraform)

1. Update `EVENT_APPEND_DB_PASSWORD` and/or `EVENT_QUERY_DB_PASSWORD` in `infra/.env`.
2. Re-apply bootstrap:

```bash
make infra-tf-bootstrap
```

3. Restart API/worker containers using rotated DB credentials.
4. Validate query and append paths with role-specific privilege checks.

## Observability Essentials

- Redpanda topic lag and consumer-group health.
- Airflow DAG success/failure and retry rates.
- Event-store append throughput and read-model freshness.
- Quarantine volume and top failure reasons.
