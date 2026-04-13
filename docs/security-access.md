# Security and Access Control

This architecture enforces least privilege and immutable audit trails across event ingestion and lakehouse processing.

## Security Principles

- Deny by default, grant explicit minimum privileges.
- Separate source ingress, transformation, and query identities.
- Keep event history append-only.
- Enforce encryption and network isolation through IaC.
- Preserve replayability for legal defensibility.
- Keep UI authentication disabled in local demo mode and rely on rate/network controls for public access.
- Project operations are not intended to run as OS root; run Docker/Make commands as a regular user.

## Identity and Access Map

| Principal | Layer | Access |
| --- | --- | --- |
| Finance uploader | MinIO | Put-only to `landing/finance/*` |
| Demo Excel generator | Keycloak + MinIO + Redpanda | Select random `finance` actor identity, upload sample files, emit ingress events |
| Scan worker | MinIO + Redpanda | Read `landing/*`, write scan verdict topics |
| Airflow worker | MinIO + Redpanda + Event DB | Read/write stage prefixes, consume/produce orchestration topics, append event-store records |
| Debezium connector | OLTP + Redpanda | Read WAL/CDC, publish `cdc.oltp.raw.v1` |
| Fraud worker | Redpanda + OLTP + MinIO | Consume CDC raw, write risk flags, publish assessed events, write bronze outputs |
| Salesforce extractor | Salesforce API + MinIO + Event DB | Pull raw responses, persist raw artifacts, append pull events |
| UI query API | Event DB read models | Read-only run/lineage/artifact/alert views |
| Trino analyst path | Iceberg/MinIO | Read `silver/*` only |
| Trino executive path | Iceberg/MinIO | Read `gold/*` only |

## Network Isolation

- Processing services run on internal Docker networks with no host-published ports.
- Public ingress is limited to explicit surfaces:
  - UI application.
  - Read-only query API.
  - Required admin consoles in local development.
- Ingress services do not require direct internet inbound paths.
- Public UI mode means no user login dependency in the request path.
- Vault and KES run on `platform_internal` only and are not host-reachable.

## Encryption Model

### At Rest

- MinIO uses SSE-KMS with KES/Vault-managed keys.
- Bucket policies deny `PutObject` unless SSE-KMS headers are present for:
  - `bronze/*`
  - `silver/*`
  - `gold/*`
  - `quarantine/*`
- Current phase keeps `landing/*` and `raw/*` writable without mandatory SSE-KMS headers.
- Enforced write headers:
  - `x-amz-server-side-encryption=aws:kms`
  - `x-amz-server-side-encryption-aws-kms-key-id=<approved key id>`

### In Transit

- TLS is required for external interfaces in deployment environments.
- Local development may use non-TLS for convenience, but architecture assumes TLS-capable endpoints.

## Kafka/Redpanda Controls

- Topic ACLs enforce producer/consumer separation per service identity.
- Consumers use dedicated groups for deterministic replay control.
- Retention and compaction policies must preserve forensic replay requirements.

## Database Controls

### Event Store Database

- `event_append_runtime` is the write-path runtime login and is bound to `event_store_appender`.
- `event_query_runtime` is the UI/API read-path runtime login and is bound to `event_store_reader`.
- Pipeline write path is append-only on event tables.
- No `UPDATE`/`DELETE` privileges for appender or query principals.
- Read-model builders can write materialized read tables in isolated schemas.
- Current local baseline grants UI query reads on `event_store` tables through `event_store_reader`; this is narrowed to read-model-only schemas once those schemas are introduced.

### OLTP Source Database

- Debezium has read-only CDC privileges.
- Fraud worker has minimal write rights only for fraud-flag columns/tables.

## Data-Layer Security Intent

- Bronze: source-faithful, restricted access, PII allowed for forensic and compliance use.
- Silver: deduplicated and masked/de-identified for analyst workflows.
- Gold: KPI-only business summaries without direct PII.

## Immutability and Legal Defensibility

- No history rewriting in event topics or event-store records.
- Corrections are represented as new events.
- Bronze keeps ordering and provenance metadata (offsets, LSN, checksums).
- Replay procedures are part of standard operations.

## UI Alerting Policy

- Alerts are published as events and surfaced in UI feed read models.
- Slack integration is out of scope for this local reference architecture.

## Rotation Posture

- Vault transit key rotation increments key version and is non-destructive for existing ciphertext.
- MinIO service-user credential rotation is applied through Terraform.
- Event-store runtime credential rotation is applied through Terraform role password updates.
- See [operations.md](operations.md) for command-level procedures.
