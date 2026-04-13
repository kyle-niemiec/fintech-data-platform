# Operations

This runbook defines the local event-driven operating sequence.

## Prerequisites

- Docker + Docker Compose
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

1. Initialize Terraform providers:

```bash
make infra-tf-init
```

2. Start core stateful services (Postgres, event-store DB, Vault/KES, MinIO, Redpanda):

```bash
docker compose -f infra/docker-compose.yaml --env-file infra/.env up -d postgres event_store_db vault kes minio redpanda
```

`vault_bootstrap` and `kes_bootstrap` run automatically as one-shot dependencies during this step.

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

7. Build and start the UI query API container:

```bash
make api-install
make api-dev
```

The API is exposed at `http://localhost:8000` and connects to event-store Postgres over Docker-internal networking.

## Internal Service Access (No Data-Plane Host Ports)

- Postgres/event-store/MinIO/Redpanda are intentionally not published to host ports.
- Vault/KES are also internal-only and not host-published.
- Use container-exec paths for local diagnostics:

```bash
make db-psql-core
make db-psql-event-store
docker compose -f infra/docker-compose.yaml --env-file infra/.env exec minio sh
docker compose -f infra/docker-compose.yaml --env-file infra/.env exec redpanda rpk cluster info
docker compose -f infra/docker-compose.yaml --env-file infra/.env exec vault sh
docker compose -f infra/docker-compose.yaml --env-file infra/.env logs kes --tail=50
```

## KMS Readiness Checks

1. Verify Vault transit key exists:

```bash
docker compose -f infra/docker-compose.yaml --env-file infra/.env exec -T vault sh -ec 'export VAULT_ADDR=http://127.0.0.1:8200; export VAULT_TOKEN="$VAULT_DEV_ROOT_TOKEN_ID"; vault read transit/keys/fintech-minio-kms-root'
```

2. Verify KES started against Vault:

```bash
docker compose -f infra/docker-compose.yaml --env-file infra/.env logs kes --tail=50
```

3. Verify MinIO is up with KES endpoint configured:

```bash
docker compose -f infra/docker-compose.yaml --env-file infra/.env logs minio --tail=50
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
docker compose -f infra/docker-compose.yaml --env-file infra/.env exec -T vault sh -ec 'export VAULT_ADDR=http://127.0.0.1:8200; export VAULT_TOKEN="$VAULT_DEV_ROOT_TOKEN_ID"; vault write -f transit/keys/fintech-minio-kms-root/rotate; vault read -field=latest_version transit/keys/fintech-minio-kms-root'
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
