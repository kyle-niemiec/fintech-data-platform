# Development Roadmap

This roadmap is ordered around event-driven delivery, not API-first delivery.

## Phase 1 - Event-Driven Foundation

- Add Redpanda as canonical broker.
- Add dedicated event-store database.
- Wire MinIO bucket notifications to Redpanda.
- Define topic ACLs and service identities in Terraform.
- Establish internal Docker network boundaries for processing services.
- Lock partitioning standards for topics, event-store tables, and object paths.

## Phase 2 - Security Baseline and Encryption

- Enforce MinIO SSE-KMS via KES/Vault.
- Add bucket-policy enforcement for encrypted writes.
- Define append-only database role permissions for event storage.
- Add key rotation and credential rotation runbook guidance.

## Phase 3 - Excel Pipeline

- Implement ClamAV scanning workflow.
- Implement file size/type gating.
- Implement Airflow validation DAG with raw/quarantine branching.
- Persist structured validation events and artifact lineage.
- Emit bronze-ready events.

## Phase 4 - CDC and Fraud Pipeline

- Add OLTP simulation and Debezium CDC connector.
- Implement fraud worker (single container runtime).
- Emit assessed CDC events.
- Persist source-faithful CDC bronze data including offsets and LSN.

## Phase 5 - Salesforce Pipeline

- Add mock Salesforce service and incremental pull logic.
- Implement scheduled and manual pull DAG triggers.
- Persist pull cursor history and raw response artifacts.
- Emit bronze-ready events for CRM objects.

## Phase 6 - Curated Layer Orchestration

- Implement bronze-to-silver DAG with dedupe, masking, and SCD2 controls.
- Implement silver-to-gold DAG with KPI aggregation.
- Emit stage completion/failure events for all curated transitions.

## Phase 7 - Query Plane and UI

- Implement read-model builders from event-store and stage events.
- Reframe FastAPI as read-only UI query API.
- Implement UI run explorer, lineage trace, artifact explorer, and alert feed.
- Add UI-triggered demo-data generation via source-adapter services.

## Phase 8 - Replay and Observability Hardening

- Add replay tooling for topic offset and run-scoped backfills.
- Add DAG/event lag dashboards and failure analytics.
- Add deterministic recovery playbooks for each source pipeline.

## Phase 9 - Portfolio Hardening

- Add end-to-end scenario fixtures (success, schema fail, fraud fail, replay).
- Add architecture diagrams and evidence pack for interview walkthroughs.
- Add local-to-cloud portability notes while preserving local-first stack.
