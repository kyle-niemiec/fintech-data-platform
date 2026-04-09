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

Authentication is delegated to Keycloak (OIDC), not issued by the API.

- Human users (`operator`, `observer`) authenticate through Authorization Code + PKCE.
- Pipeline services authenticate through Client Credentials using the `meridian-pipeline` client.
- Realm/clients/roles/users are provisioned declaratively via Terraform (`infra/terraform/identity/keycloak.tf`).
- API access tokens are RS256-signed by Keycloak and validated by the API against:
  - issuer (`iss`) = configured realm URL
  - audience (`aud`) = `meridian-api`
  - signature + expiry
- Role authorization is still API-local and role-based:
  - `operator`/`observer`/`pipeline` are read from Keycloak client roles under `resource_access.meridian-api.roles`.
  - API role definitions and role groups are centralized in `backend/app/domain/authz.py` (`ApiRole`, observer/writer role sets).
  - Tokens with no recognized API role or multiple API roles are rejected.
- Operator routes use DB session `api_runtime` (`control_plane_writer`), observer routes use `audit_runtime` (`control_plane_reader`), and pipeline routes use `api_pipeline` (`ingestion_writer`).
- Trade-off and auditability: DB sessions are still reduced to role-level service users, but every write persists token actor attribution (`actor_sub` + `actor_role`) on `ingestion_run`, `artifact`, and `lineage_record` so actions remain traceable to the calling identity.

## Postgres RBAC

Roles are defined as `NOLOGIN` templates in `infra/db/migrations/04_create_roles.sql`. Login users are provisioned and bound to those templates by Terraform in `infra/terraform/bootstrap/postgres.tf`.

**Role responsibilities:**

- `db_migrator` — DDL ownership, full data access. Used only for running migrations.
- `control_plane_writer` — `SELECT, INSERT` on `ingestion_run`; `UPDATE (status, completed_at)` on `ingestion_run`; `SELECT, INSERT` on `artifact` and `lineage_record`. Bound to `api_runtime`.
- `control_plane_reader` — `SELECT` on all three control-plane tables. Bound to `audit_runtime`.
- `ingestion_writer` — `SELECT, INSERT` on all three tables; `UPDATE (status, completed_at)` on `ingestion_run`. Bound to `airflow_runtime` or equivalent pipeline service user.

`ALTER DEFAULT PRIVILEGES FOR ROLE db_migrator` ensures future tables created by migrations automatically inherit grants without manual re-grants per migration file.

## MinIO Policies

MinIO bucket, IAM users, and IAM policies are provisioned by Terraform in `infra/terraform/bootstrap/minio.tf`. Bucket ARN defaults to `fintech-lakehouse` and is configurable via `MINIO_BUCKET_NAME`.

| Policy resource | Principal | Access |
| --- | --- | --- |
| `minio_iam_policy.ingest` | Ingest service | List + read/write `landing/`, `raw/` |
| `minio_iam_policy.transform` | Transform service | Read `raw/`; write `bronze/`, `silver/`, `gold/`, `quarantine/` |
| `minio_iam_policy.trino_write` | Trino Iceberg connector | Read all curated layers; write Iceberg metadata files to `bronze/`, `silver/`, `gold/` |
| `minio_iam_policy.trino_read` | Trino BI path | Read-only `silver/`, `gold/` only |

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
- **Secrets:** Runtime credentials supplied via environment variables or a secret manager. For local provisioning, Docker Compose and Terraform both read from `infra/.env` (Terraform via Make-exported `TF_VAR_*`), including `KC_PIPELINE_CLIENT_SECRET` and MinIO IAM user secrets. Rotate Keycloak admin/client secrets and MinIO access secrets on a schedule in long-lived deployments.
