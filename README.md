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

## Quick Start

```bash
cp infra/.env.example infra/.env
cp backend/.env.example backend/.env
# Fill in secrets in both .env files (the backend values must match the
# Keycloak realm/client/audience that the identity Terraform provisions).

python3 -m venv backend/.venv

make infra-tf-init
make infra-pg-up
make infra-tf-bootstrap
make infra-kc-up
# Wait for Keycloak readiness before identity apply (container "Up" and startup
# log line like "Listening on: http://0.0.0.0:8080").
make infra-tf-apply

make api-install
make api-dev
```

The API then runs at `http://127.0.0.1:8000` with Swagger at `/docs`. See [docs/operations.md](docs/operations.md) for the full operational guide, including the staged startup rationale and Makefile target reference.

## What Is Implemented Right Now

Phases 1, 2, and 3 are complete:

- Infrastructure via Docker Compose + Terraform:
  - PostgreSQL (`fintech_postgres`)
  - MinIO (`fintech_minio`)
  - Keycloak (`fintech_keycloak`)
  - Terraform is split into a `bootstrap/` phase (Postgres roles, Keycloak DB schema ownership, MinIO bucket/users/policies) and an `identity/` phase (Keycloak realm, clients, roles, users). The split exists because Keycloak needs DB credentials before it can start, while the identity Terraform needs a running Keycloak API to talk to. See [docs/operations.md](docs/operations.md) for the staged startup sequence.
- Database migrations:
  - `ingestion_run`, `artifact`, `lineage_record` tables
  - Regulated-style enum domains (`ingestion_source`, `ingestion_status`, `artifact_stage`, `artifact_format`)
  - Least-privilege role templates (`db_migrator`, `control_plane_writer`, `control_plane_reader`, `ingestion_writer`)
- Backend control plane API:
  - `POST /runs/` — create ingestion run (operator, pipeline)
  - `GET /runs/` — list all runs, newest first (observer+)
  - `GET /runs/{run_id}` — fetch one run (observer+)
  - `POST /artifacts/` — register an artifact for a run (operator, pipeline)
  - `GET /artifacts/` — list artifacts for a run (observer+)
  - `GET /artifacts/{artifact_id}` — fetch one artifact (observer+)
  - `POST /lineage/` — register a lineage relationship (operator, pipeline)
  - `GET /lineage/` — list lineage records for a run (observer+)
- Security:
  - Keycloak OIDC for auth (Authorization Code + PKCE for users via the `meridian-api` client, Client Credentials for services via the `meridian-pipeline` client)
  - Strict JWT validation in API (`iss`, `aud`, RS256 signature, expiry)
  - Split DB connections enforcing Postgres RBAC at the connection level
  - Terraform-managed MinIO IAM policies for ingest, transform, and Trino service accounts
  - Trino file-based access control rules stub at [infra/trino/access-control/rules.json](infra/trino/access-control/rules.json) (populated in Phase 7+)

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
| [docs/operations.md](docs/operations.md) | Quickstart, Makefile targets, env setup, Terraform provisioning flow |
| [docs/roadmap.md](docs/roadmap.md) | All 11 phases with status and deliverables |

## Note

This project is intended to demonstrate engineering judgment and production-minded architecture in a portfolio context. It does not claim audited or certified compliance.
