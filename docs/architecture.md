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
    dependencies.py     — request-scoped DB session selection by API role
    domain/
      authz.py          — API role enum + authorization role groups
      enums.py          — Python enums mirroring DB enum types
    models/
      ingestion_run.py  — SQLAlchemy ORM model
      artifact.py
      lineage_record.py
    routes/
      ingestion_run.py  — POST /runs, GET /runs, GET /runs/{id}
      artifact.py       — POST /artifacts, GET /artifacts, GET /artifacts/{id}
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
  data-model.md
  security-access.md
  api-control-plane.md
  operations.md
  roadmap.md

infra/
  docker-compose.yaml
  .env.example
  db/
    migrations/
      01_create_enums.sql
      02_create_tables.sql
      03_custom_constraints.sql
      04_create_roles.sql
  make/
    terraform-env.mk    — exports infra/.env values as TF_VAR_* for Terraform
  terraform/
    README.md           — provisioning workflow notes
    bootstrap/
      providers.tf      — Terraform provider config (Postgres, MinIO)
      versions.tf       — required provider versions
      postgres.tf       — Runtime DB login users + Keycloak schema ownership
      minio.tf          — Bucket, IAM users, IAM policies, attachments
      variables.tf      — Bootstrap Terraform input contract
      outputs.tf        — Bootstrap Terraform outputs
    identity/
      providers.tf      — Terraform provider config (Keycloak)
      versions.tf       — required provider versions
      keycloak.tf       — Realm, clients, roles, users, role bindings
      variables.tf      — Identity Terraform input contract
      outputs.tf        — Identity Terraform outputs
  trino/
    access-control/
      rules.json        — file-based system access control stub (Phase 7+)

ui/
```

### Why Terraform Is Split Into Two Phases

The `bootstrap/` and `identity/` configurations have separate state files and are applied at different points in the staged startup. The split exists to break a chicken-and-egg dependency: Keycloak needs Postgres credentials and a `keycloak` schema before it can boot, but the Keycloak Terraform provider needs a running Keycloak API to talk to. The bootstrap phase runs against Postgres + MinIO before Keycloak starts; the identity phase runs once Keycloak is up. The service lifecycle (container start/stop) stays in Docker Compose. See [docs/operations.md](operations.md) for the staged sequence and [infra/terraform/README.md](../infra/terraform/README.md) for the workflow reference.

### Identity Model

Keycloak is the source of truth for human and service identities. The realm, clients, roles, users, and role bindings are all provisioned by the identity Terraform phase ([infra/terraform/identity/keycloak.tf](../infra/terraform/identity/keycloak.tf)). There is no `user_principal` table in the application database — API role authorization reads from the validated JWT (`resource_access.meridian-api.roles`) and routes to a role-specific DB session.

Two Keycloak clients exist:

- `meridian-api` — public client used by Swagger UI and human users via Authorization Code + PKCE.
- `meridian-pipeline` — confidential client used by service accounts via Client Credentials.

Both issue tokens with `aud=meridian-api` so the API audience check is unified.
