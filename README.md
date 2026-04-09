# Fintech Data Platform

Compliance-aligned, lakehouse-oriented data engineering platform designed to simulate regulated financial data operations.

This project emphasizes traceability first: every pipeline execution is modeled as a run, every dataset snapshot is tracked as an artifact, and every transformation relationship is captured as lineage.

## Project Goals

- Build a resume-grade, production-like platform for financial data workflows.
- Demonstrate senior data engineering design in control plane and data plane separation.
- Prioritize auditability, replayability, data lineage, and immutable data handling patterns.
- Align architecture choices with regulated-environment expectations (FINRA/SOC 2 style controls) without claiming certification.

## Compliance Positioning

This repository is compliance-aligned by design, not compliance-certified.

Implemented patterns include:

- Immutable-style run/event recording with UUID identifiers and timestamps.
- Explicit lifecycle/state modeling via Postgres enums.
- First-class lineage and artifact schema design for end-to-end traceability.
- Environment-based secret/config handling (`.env`, not hardcoded credentials).
- Least-privilege role and policy templates for Postgres, MinIO, and Trino.

## Architecture at a Glance

```text
Control Plane (metadata + orchestration visibility)
  FastAPI + SQLAlchemy + Postgres
    └── Ingestion Runs API

Data Plane (payload movement and transformation)
  Airflow / CDC / CRM ingestion (planned)
  MinIO object storage — landing / raw / bronze / silver / gold / quarantine
  Trino + Iceberg query layer (planned)
```

Core domain model:

```text
Run --> Artifacts --> Lineage
```

See [docs/architecture.md](docs/architecture.md) for the full control/data plane breakdown, domain model schema, and data flow diagram.

## What Is Implemented Right Now

Phase 1 and Phase 2 are complete:

- Infrastructure via Docker Compose:
  - PostgreSQL (`fintech_postgres`)
  - MinIO (`fintech_minio`)
- Database migrations:
  - `ingestion_run`, `artifact`, `lineage_record` tables
  - Regulated-style enum domains (`ingestion_source`, `ingestion_status`, `artifact_stage`, `artifact_format`)
  - Least-privilege role templates (`db_migrator`, `control_plane_writer`, `control_plane_reader`, `ingestion_writer`)
- Backend control plane API:
  - `POST /runs/` — create ingestion run (operator and pipeline)
  - `GET /runs/` — list all runs, newest first (observer+)
  - `GET /runs/{run_id}` — fetch one run (observer+)
- Security:
  - Keycloak OIDC for auth (Authorization Code + PKCE for users, Client Credentials for services)
  - Strict JWT validation in API (`iss`, `aud`, RS256 signature, expiry)
  - Split DB connections enforcing Postgres RBAC at the connection level
  - MinIO policy set for ingest, transform, and Trino service accounts
  - Trino file-based access control rules stub

## Why This Design Is Strong (Employer View)

- **Run-centric architecture:** Every operation binds to `run_id`, enabling deterministic trace and replay boundaries.
- **Explicit domain vocabulary:** Enums enforce operational states and source types at the database boundary.
- **Future-proof modeling:** Artifact and lineage tables are in place before transformation pipelines are built.
- **Real RBAC enforcement:** DB least-privilege is enforced at the connection level — not just application logic. Separate login users per API role.
- **Separation of concerns:** Control plane metadata APIs are isolated from data movement. Data consumers query via Trino, not the control plane.

## Goals Mapped to Implementations

| Goal | Concrete Implementation |
| --- | --- |
| Auditability and traceability | `ingestion_run` table + API + UUID/timestamp metadata |
| Data lineage readiness | `lineage_record` schema with artifact FK constraints and indexes |
| Immutable, append-oriented lifecycle | Create/read API surface only — no destructive run endpoints |
| Governance via controlled vocabulary | Postgres enum types for source, status, stage, and format |
| Control vs data plane separation | FastAPI/Postgres control plane; MinIO + Trino data plane (staged rollout) |
| Least-privilege and data security | Postgres RBAC templates, split DB sessions, MinIO policies, Trino ACL rules |

## Documentation

| Document | Contents |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | Control/data plane, domain model, data flow, repo structure |
| [docs/data-model.md](docs/data-model.md) | Source contracts, bronze/silver/gold schemas, 3NF design, SCD Type 2, PII inventory |
| [docs/security-access.md](docs/security-access.md) | RBAC, auth, Trino access control, PII posture, encryption |
| [docs/api-control-plane.md](docs/api-control-plane.md) | Endpoint reference, auth flow, curl examples |
| [docs/operations.md](docs/operations.md) | Quickstart, Makefile targets, env setup, DB user creation |
| [docs/roadmap.md](docs/roadmap.md) | All 11 phases with status and deliverables |

## Note

This project is intended to demonstrate engineering judgment and production-minded architecture in a portfolio context. It does not claim audited or certified compliance.
