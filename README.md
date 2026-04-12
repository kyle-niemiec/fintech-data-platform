# Fintech Data Platform

Event-driven, compliance-aligned data engineering platform for local-first demos with infrastructure defined as code.

This repository follows the architecture in [project-planning.md](project-planning.md):
- ETL is source-triggered and event-driven.
- FastAPI serves the UI with read-only query endpoints.
- Pipeline execution remains independent if the API is offline.

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
- Pipeline metadata writes do not pass through API endpoints.
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

See [docs/operations.md](docs/operations.md) for the canonical startup and validation sequence.

## Documentation

| Document | Purpose |
| --- | --- |
| [docs/architecture.md](docs/architecture.md) | End-to-end event-driven architecture and component boundaries |
| [docs/source-pipelines.md](docs/source-pipelines.md) | Excel, CDC, and Salesforce source ingestion flows |
| [docs/event-contracts.md](docs/event-contracts.md) | Kafka topic taxonomy, envelope requirements, ordering/idempotency rules |
| [docs/partitioning-strategy.md](docs/partitioning-strategy.md) | Partitioning plan for event topics, event-store DB, and object storage paths |
| [docs/data-model.md](docs/data-model.md) | Event store schema and bronze/silver/gold data model contract |
| [docs/ui-query-api.md](docs/ui-query-api.md) | Read-only FastAPI contract for UI status, lineage, artifacts, and alerts |
| [docs/security-access.md](docs/security-access.md) | IAM/RBAC model, encryption, network isolation, immutability controls |
| [docs/operations.md](docs/operations.md) | Local runbook, environment, startup, replay, and trace validation |
| [docs/roadmap.md](docs/roadmap.md) | Execution order for building the event-driven stack |
| [docs/requirement-coverage.md](docs/requirement-coverage.md) | Mapping from `project-planning.md` requirements to concrete local components + IaC ownership |

## Compliance Positioning

This repository is compliance-aligned by architecture and controls. It does not claim formal FINRA or SOC 2 certification.
