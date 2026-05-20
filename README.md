# Fintech Data Platform

Event-driven, compliance-aligned data engineering platform for local-first demos with infrastructure defined as code.

This repository follows the planning architecture docs in [.ai/docs/planning/](.ai/docs/planning/):
- ETL is source-triggered and event-driven.
- FastAPI serves the UI with read-only query endpoints.
- UI access is anonymous for demo use (no human login dependency).
- Pipeline execution remains independent if the API is offline.

Historical concept notes are preserved in [.ai/docs/00-human-descriptions.md](.ai/docs/00-human-descriptions.md).

## Core Goals

- Demonstrate senior-level data engineering outside API-centric CRUD patterns.
- Show legally defensible ingestion and transformation lineage.
- Enforce least privilege, immutable event history, and replayable workflows.
- Keep local development low-cost while preserving production-like boundaries.

## Architecture At A Glance

```text
Sources
  Excel uploads (finance bucket writes)
  OLTP Postgres CDC (Debezium)
  Salesforce CRM pulls (Airflow)

Event Backbone
  MinIO notifications -> Redpanda (Kafka API)
  Debezium CDC -> Redpanda
  Airflow stage-complete events -> Redpanda

Processing
  ClamAV scan + file gate checks
  Airflow DAGs for validation, quarantine/raw, bronze, silver, gold
  Fraud worker (single container) on CDC stream

Storage
  MinIO lakehouse paths: landing/, raw/, quarantine/, bronze/, silver/, gold/
  Event store DB (exclusive audit/event persistence)
  Iceberg + Trino for curated analytics

Presentation
  FastAPI read-only UI query API
  UI event feed + run trace explorer
```

## Non-Negotiable Boundaries

- API is query-only for UI workflows. It does not orchestrate ETL.
- API endpoints are public in demo mode; user identity is not required for read access.
- Pipeline metadata writes do not pass through API endpoints.
- Trigger events create runs (event-first); runs are not pre-created.
- Excel/CDC/Salesforce ingestion runs are independent from curated promotion runs.
- Every cross-service transition is represented by an event on Redpanda.
- Bronze keeps source-faithful payloads for forensics/replay.
- Security controls are encoded in IaC (roles, ACLs, bucket policies, network boundaries, encryption posture).

## Security Posture

- Internal Docker networking for processing services (no public ingress except intended UI/API/admin surfaces).
- MinIO SSE-KMS (KES/Vault) with bucket-policy enforcement for encrypted writes.
- Append-only event store and topic contracts for auditability.
- Layered access model: bronze restricted, silver de-identified, gold executive-safe.

## Local Development Model

This project standardizes a local event-driven stack:
- Docker Compose runs runtime services.
- Terraform provisions identities, policies, and platform security controls.
- Airflow orchestrates source and curated DAGs from event triggers.
- Redpanda provides durable event routing, replay, and fan-out.

See [.ai/docs/planning/operations.md](.ai/docs/planning/operations.md) for the canonical startup and validation sequence.

## Repository Structure

- `apps/ui/`: public demo UI application workspace.
- `services/workers/ui-api/`: read-only FastAPI query API for the UI.
- `services/workers/`: event-driven ingestion workers (scanner, trigger bridge, bronze writer).
- `services/pipeline/`: Airflow runtime and DAGs.
- `services/libs/`: shared event contracts and runtime libraries used across services.
- `infra/`: Docker Compose, Terraform, DB migrations, KMS bootstrap, and operational tooling.

## Documentation

| Document | Purpose |
| --- | --- |
| [.ai/docs/planning/architecture.md](.ai/docs/planning/architecture.md) | End-to-end event-driven architecture and component boundaries |
| [.ai/docs/planning/source-pipelines.md](.ai/docs/planning/source-pipelines.md) | Excel, CDC, and Salesforce source ingestion flows |
| [.ai/docs/planning/event-contracts.md](.ai/docs/planning/event-contracts.md) | Kafka topic taxonomy, envelope requirements, ordering/idempotency rules |
| [.ai/docs/planning/partitioning-strategy.md](.ai/docs/planning/partitioning-strategy.md) | Partitioning plan for event topics, event-store DB, and object storage paths |
| [.ai/docs/planning/data-model.md](.ai/docs/planning/data-model.md) | Event store schema and bronze/silver/gold data model contract |
| [.ai/docs/planning/ui-query-api.md](.ai/docs/planning/ui-query-api.md) | Read-only FastAPI contract for UI status, lineage, artifacts, and alerts |
| [.ai/docs/planning/security-access.md](.ai/docs/planning/security-access.md) | IAM/RBAC model, encryption, network isolation, immutability controls |
| [.ai/docs/planning/operations.md](.ai/docs/planning/operations.md) | Local runbook, environment, startup, replay, and trace validation |
| [.ai/docs/planning/roadmap.md](.ai/docs/planning/roadmap.md) | Execution order for building the event-driven stack |
| [.ai/docs/planning/requirement-coverage.md](.ai/docs/planning/requirement-coverage.md) | Mapping from historical concept notes in `.ai/docs/00-human-descriptions.md` to concrete local components + IaC ownership |

## Compliance Positioning

This repository is compliance-aligned by architecture and controls. It does not claim formal FINRA or SOC 2 certification.
