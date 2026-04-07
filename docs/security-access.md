# Security and Access Control

Security for this project is designed around strict identity boundaries between infrastructure, API runtime, data pipeline services, and data consumers. Every principal has a named identity and accesses exactly the layer it needs — no more.

## Security Principles

- Deny by default, grant only the minimum privileges needed per service.
- Separate schema/migration power from application runtime power.
- Separate write-capable and read-only DB identities — enforced at the connection level, not just application logic.
- Data consumers never touch the control plane Postgres or MinIO directly — their access boundary is the Trino query engine.
- Record actor + action metadata for auditability.

## Principal and Access Layer Map

| Principal | Layer | Role / Policy | What they touch |
| --- | --- | --- | --- |
| FastAPI operator runtime | Postgres | `control_plane_writer` → `api_runtime` login | Write `ingestion_run`; read all three control-plane tables |
| FastAPI observer runtime | Postgres | `control_plane_reader` → `audit_runtime` login | Read-only `ingestion_run`, `artifact`, `lineage_record` |
| Airflow / pipeline services | Postgres + MinIO | `ingestion_writer` + `minio_ingest` / `minio_transform` | Full pipeline write path |
| Trino ETL / maintenance | MinIO | `minio_trino_write` | Read all curated layers + Iceberg metadata writes |
| Trino BI / analytics | MinIO | `minio_trino_read` | Read-only `silver/`, `gold/` only |
| Data scientist | Trino | `analyst` role | `silver.*` de-identified views; PII masked as secondary control |
| Executive / BI tool | Trino | `executive` role | `gold.*` only |
| Data engineer | Trino | `data_engineer` role | All schemas, full privileges |

`control_plane_reader` is an **audit/ops role** — it provides platform health inspection for operators and the ops UI. It is not a data consumer role. Data scientists and executives query curated Iceberg tables through Trino.

## API Authentication

The API uses OAuth2 Password Flow with locally signed HS256 JWTs.

- `POST /token` issues a token for `operator` or `observer` credentials (configured in `.env`).
- Each token carries a `role` claim that gates route access.
- Operator routes use a DB session bound to `api_runtime` (mapped to `control_plane_writer`).
- Observer routes use a DB session bound to `audit_runtime` (mapped to `control_plane_reader`).
- Swagger UI exposes an "Authorize" button for interactive token entry.

## Postgres RBAC

Roles are defined as `NOLOGIN` templates in `infra/db/migrations/04_create_roles.sql`. Login users are bound to roles per environment — never committed to source control.

**Role responsibilities:**

- `db_migrator` — DDL ownership, full data access. Used only for running migrations.
- `control_plane_writer` — `SELECT, INSERT` on `ingestion_run`; `UPDATE (status, completed_at)` on `ingestion_run`; `SELECT` on `artifact` and `lineage_record`. Bound to `api_runtime`.
- `control_plane_reader` — `SELECT` on all three control-plane tables. Bound to `audit_runtime`.
- `ingestion_writer` — `SELECT, INSERT` on all three tables; `UPDATE (status, completed_at)` on `ingestion_run`. Bound to `airflow_runtime` or equivalent pipeline service user.

`ALTER DEFAULT PRIVILEGES FOR ROLE db_migrator` ensures future tables created by migrations automatically inherit grants without manual re-grants per migration file.

**Binding login users (run manually per environment):**

```sql
CREATE ROLE api_runtime LOGIN PASSWORD '<secret>';
GRANT control_plane_writer TO api_runtime;

CREATE ROLE audit_runtime LOGIN PASSWORD '<secret>';
GRANT control_plane_reader TO audit_runtime;

CREATE ROLE airflow_runtime LOGIN PASSWORD '<secret>';
GRANT ingestion_writer TO airflow_runtime;
```

## MinIO Policies

All MinIO policies are in `infra/minio/policies/`. Bucket ARN is `fintech-lakehouse` — adjust if your bucket name differs.

| Policy file | Principal | Access |
| --- | --- | --- |
| `minio_ingest_policy.json` | Ingest service | List + read/write `landing/`, `raw/` |
| `minio_transform_policy.json` | Transform service | Read `raw/`; write `bronze/`, `silver/`, `gold/`, `quarantine/` |
| `minio_trino_write_policy.json` | Trino Iceberg connector | Read all curated layers; write Iceberg metadata files to `bronze/`, `silver/`, `gold/` |
| `minio_trino_read_policy.json` | Trino BI path | Read-only `silver/`, `gold/` only |

No consumer identity has direct MinIO access. The `minio_trino_read` policy exists for a BI-only Trino cluster or secondary query path with no catalog maintenance responsibilities.

## Trino Access Control (Phase 7+)

Data consumers access curated Iceberg data through Trino using file-based system access control (`infra/trino/access-control/rules.json`).

**Role scopes:**

- `data_engineer` — all schemas, full privileges. Used for debugging, replay, and pipeline development.
- `analyst` — `silver.*` only. PII schema separation is the **primary control**: `silver_pii.*` tables are `data_engineer`-only; `silver.*` exposes de-identified views. Column masking in `rules.json` is a secondary belt-and-suspenders control on top of the de-identified views.
- `executive` — `gold.*` only. No raw or PII-adjacent fields in the gold schema by design.

Column masks are stubbed in `rules.json` now and populated when the silver schema is defined in Phase 8.

## Encryption Posture

- **In transit:** TLS for FastAPI, Postgres, and MinIO in deployment environments. Not enforced locally.
- **At rest:** Postgres on encrypted volumes; MinIO SSE-S3 or SSE-KMS preferred in production-like setups.
- **Secrets:** No credentials in source control. Runtime credentials supplied via environment variables or a secret manager. `SECRET_KEY` for JWT signing should be rotated on a schedule in long-lived deployments.
