# Architecture

## Control Plane vs Data Plane

The platform is split into two distinct layers with no shared runtime dependencies.

**Control Plane** handles metadata, orchestration visibility, and audit tracking. It knows _that_ data moved, _when_, and _what_ the outcome was — but never holds the data itself.

```
FastAPI + SQLAlchemy + Postgres
  ├── ingestion_run   — pipeline execution records
  ├── artifact        — dataset snapshots at each stage
  └── lineage_record  — transformation relationships between artifacts
```

**Data Plane** handles ingestion, transformation, and storage of actual payloads.

```
MinIO (object storage)
  ├── landing/      — raw file drop, pre-validation
  ├── raw/          — validated, schema-checked
  ├── bronze/       — Parquet, schema-enforced, append-only
  ├── silver/       — cleaned, deduped, PII-masked (Trino: analyst)
  ├── gold/         — aggregated KPIs (Trino: executive)
  └── quarantine/   — failed records at any stage

Trino + Iceberg (Phase 7+)
  — query engine and access enforcement layer for silver/gold
  — data consumers never access MinIO directly
```

This separation means the control plane can be queried for operational audit without touching the data itself, and the data plane can evolve (new layers, new formats) without changing the metadata model.

## Core Domain Model

```
Run --> Artifacts --> Lineage
```

Every action in the system traces back to a `run_id`.

**ingestion_run**

| Field | Type | Notes |
| --- | --- | --- |
| `run_id` | UUID | Primary key, generated in application |
| `source_type` | enum | `excel_upload`, `salesforce_crm`, `transaction_cdc` |
| `status` | enum | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `actor_sub` | text | Token subject (`sub`) for the caller that created the row |
| `actor_role` | text | Effective API role used for DB session routing (`operator`, `observer`, `pipeline`) |
| `started_at` | timestamptz | Set at creation |
| `completed_at` | timestamptz | Nullable; set on terminal state |

**artifact**

| Field | Type | Notes |
| --- | --- | --- |
| `artifact_id` | UUID | Primary key |
| `run_id` | UUID | FK → ingestion_run |
| `stage` | enum | `landing`, `raw`, `bronze`, `silver`, `gold`, `quarantine` |
| `format` | enum | `csv`, `json`, `parquet`, `xlsx` |
| `storage_path` | text | MinIO object path |
| `actor_sub` | text | Token subject (`sub`) for the caller that created the row |
| `actor_role` | text | Effective API role used for DB session routing |
| `created_at` | timestamptz | |

**lineage_record**

| Field | Type | Notes |
| --- | --- | --- |
| `lineage_id` | UUID | Primary key |
| `run_id` | UUID | FK → ingestion_run |
| `input_artifact_id` | UUID | FK → artifact |
| `output_artifact_id` | UUID | FK → artifact |
| `transformation` | text | Description of the operation |
| `actor_sub` | text | Token subject (`sub`) for the caller that created the row |
| `actor_role` | text | Effective API role used for DB session routing |
| `created_at` | timestamptz | |

A check constraint enforces `input_artifact_id != output_artifact_id`.

## Data Flow (Excel Vertical Slice)

```
Upload .xlsx
    │
    ▼
[landing/run_id/file.xlsx]         artifact: stage=landing, format=xlsx
    │  schema validation
    ▼
[raw/run_id/file.csv]              artifact: stage=raw, format=csv
    │  Parquet conversion
    ▼
[bronze/run_id/file.parquet]       artifact: stage=bronze, format=parquet
    │                              lineage: landing → bronze
    ▼
[silver/run_id/table/]             artifact: stage=silver (Phase 8)
    │  PII masking, dedup
    ▼
[gold/run_id/kpi_summary/]         artifact: stage=gold (Phase 9)
```

Each arrow produces a `lineage_record` linking the input and output artifacts under the same `run_id`.

## Repository Structure

```
backend/
  app/
    auth.py             — Keycloak JWT validation, role guards
    config.py           — pydantic-settings, split DB URL + Keycloak settings
    db.py               — operator/observer/pipeline engines, session factories
    domain/
      authz.py          — API role enum + authorization role groups
      enums.py          — Python enums mirroring DB enum types
    models/
      ingestion_run.py  — SQLAlchemy ORM model
    routes/
      ingestion_run.py  — POST /runs, GET /runs, GET /runs/{id}
      artifact.py       — POST /artifacts, GET /artifacts
      lineage_record.py — POST /lineage, GET /lineage
    schemas/
      ingestion_run.py  — IngestionRunCreate, IngestionRunRead
      artifact.py       — ArtifactCreate, ArtifactRead
      lineage_record.py — LineageRecordCreate, LineageRecordRead
    main.py             — FastAPI app, router registration
  requirements.txt
  .env.example

docs/
  architecture.md
  security-access.md
  api-control-plane.md
  operations.md
  roadmap.md

infra/
  docker-compose.yaml
  db/
    migrations/
      01_create_enums.sql
      02_create_tables.sql
      03_custom_constraints.sql
      04_create_roles.sql
      05_create_login_roles.sql
  keycloak/
    meridian-realm.json
  minio/
    policies/
      minio_ingest_policy.json
      minio_transform_policy.json
      minio_trino_write_policy.json
      minio_trino_read_policy.json
  trino/
    access-control/
      rules.json

ui/
```
