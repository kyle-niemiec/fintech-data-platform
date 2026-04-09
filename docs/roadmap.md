# Development Roadmap

## Phase 1 — Control Plane Foundation ✅

- DB schema: enums, tables (`ingestion_run`, `artifact`, `lineage_record`), indexes, constraints
- Docker Compose: Postgres, MinIO
- FastAPI backend skeleton with SQLAlchemy + psycopg
- `POST /runs`, `GET /runs`, `GET /runs/{run_id}`

## Phase 2 — Security & Auth ✅

- Postgres RBAC overhaul (`04_create_roles.sql`): differentiated writer roles, `REVOKE PUBLIC`, owner-aware `DEFAULT PRIVILEGES`
- MinIO policy set finalized: `minio_ingest`, `minio_transform`, `minio_trino_write`, `minio_trino_read`
- Trino access control rules stub (`infra/trino/access-control/rules.json`)
- API authentication delegated to Keycloak OIDC:
  - humans via Authorization Code + PKCE
  - service identities via Client Credentials
  - strict JWT validation (`iss`, `aud`, RS256 signature, expiry)
- Split DB sessions: operator routes use `api_runtime`, observer routes use `audit_runtime`, pipeline routes use `api_pipeline`

## Phase 3 — Artifact Tracking APIs

- `POST /artifacts` (operator only)
- `GET /artifacts?run_id=` (observer+)
- `GET /artifacts/{id}` (observer+)
- `POST /lineage` (operator only)
- `GET /lineage?run_id=` (observer+)
- Link artifacts and lineage records to runs; persist MinIO storage paths

## Phase 4 — Excel Pipeline (First Vertical Slice)

- File upload endpoint → store to MinIO `landing/`
- Create ingestion run via control plane
- Schema validation → Parquet conversion → `raw/`
- Bronze promotion
- Artifact + lineage records written by pipeline service (`ingestion_writer` / `airflow_runtime`)

## Phase 5 — CDC Pipeline

- Postgres OLTP simulation source DB
- Debezium + Kafka setup
- Bronze storage of CDC events
- Fraud detection service hook

## Phase 6 — CRM Pipeline

- Mock Salesforce API
- Airflow batch extraction
- Incremental pulls, bronze storage

## Phase 7 — Lakehouse Foundation (Trino + Iceberg)

- Add Trino + Iceberg (+ Nessie or Hive Metastore) to Docker Compose
- Wire `minio_trino_write` credentials into Trino Iceberg connector config
- Enable file-based system access control (`infra/trino/access-control/rules.json`)
- `data_engineer` Trino role functional end-to-end
- Makefile target for Trino shell

## Phase 8 — Silver Layer

- Data cleaning, deduplication, SCD Type 2
- PII schema separation: `silver_pii.*` (raw, `data_engineer` only) + `silver.*` (de-identified views, `analyst` accessible)
- Column masking rules populated in `infra/trino/access-control/rules.json` as secondary control
- `analyst` Trino role functional: `silver.*` queryable with PII masked

## Phase 9 — Gold Layer

- KPI tables, aggregations, business metrics
- `executive` Trino role functional: `gold.*` only — no raw fields in schema

## Phase 10 — UI Layer

- Run Explorer — backed by `control_plane_reader` / `audit_runtime` (audit view of pipeline health)
- Artifact Viewer
- Failure Viewer
- Demo data generator
- Business data in UI flows through Trino query API — not the control plane Postgres

## Phase 11 — Observability & Ops

- Notification system
- Event logging
- Pipeline replay
- Pipeline metrics
