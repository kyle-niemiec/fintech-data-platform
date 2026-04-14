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
COMPOSE_FILES="-f infra/docker-compose.yaml -f infra/compose/foundation.yaml -f infra/compose/orchestration.yaml -f infra/compose/excel-pipeline.yaml -f infra/compose/api.yaml -f infra/compose/ui.yaml"
```

Run the staged infra bootstrap first (single command):

```bash
make infra-up
```

Or run individual steps:

```bash
make infra-up 1
make infra-up 2
make infra-up 3
make infra-up 4
make infra-up 5
make infra-up 6
make infra-up 7
make infra-up 8
make infra-up 9
```

The staged flow includes the read-only UI query API (`make infra-up 7`) and demo UI (`make infra-up 8`).
The API is exposed at `http://localhost:8000` and the UI is exposed at `http://localhost:3000`.

### Development override: MinIO console on host

By default, MinIO remains internal-only. For local development that needs browser access to MinIO (`:9001`), use:

```bash
make infra-up-dev
```

This enables the dev override compose file (`infra/compose/dev-ui-access.yaml`) and publishes:
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

### Pending pipelines (later roadmap phases)

- CDC/Fraud validation is Phase 4.
- Salesforce pull validation is Phase 5.
- Curated promotion validation is Phase 6.

Do not expect CDC/Salesforce/curated runtime services in Phase 3 bring-up.

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
