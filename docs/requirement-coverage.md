# Requirement Coverage Matrix

This matrix maps `project-planning.md` requirements to local event-driven components and IaC ownership.

| Requirement Theme | Local Implementation | IaC Owner |
| --- | --- | --- |
| Excel upload triggers ingestion | Finance upload to MinIO landing prefix; object-created event emits to Redpanda | Terraform (bucket policy + notification), Compose (MinIO + Redpanda) |
| Virus, type, and size checks | ClamAV scanner and file-gate worker consume upload event and emit verdict events | Compose service definitions, Terraform service identities/ACLs |
| Airflow-driven schema validation | Airflow DAG validates Excel payload and routes raw vs quarantine | Airflow DAG code + Compose orchestration |
| Quarantine on validation fail | Validation DAG writes quarantine artifact and failure event | Airflow DAG + MinIO policy IaC |
| Raw file traceability linked to run IDs | Event-store `file_ingress` records map run IDs to landing/raw/quarantine URIs | SQL migrations + Terraform DB roles |
| Bronze conversion from valid Excel | Airflow conversion task writes Parquet to bronze and emits bronze-ready event | Airflow DAG + MinIO policy IaC |
| OLTP CDC via Debezium/DMS equivalent | Debezium captures WAL changes and publishes raw CDC topics | Compose connectors + Terraform topic ACLs |
| CDC fraud detection subscriber | Fraud worker consumes CDC raw topics, scores risk, emits assessed events, flags OLTP records | Compose runtime + Terraform identities |
| CDC bronze persistence with metadata | Bronze writer persists assessed payload with topic metadata and LSN fields | Airflow/worker code + data model contract |
| Salesforce batch pull (scheduled) | Airflow incremental pulls with cursor tracking and auditable pull events; no API/UI initiation path | Airflow DAG + Compose + Terraform secrets |
| Failure retry and auditable logging | Airflow retry policy emits attempt/failure events into event store | Airflow DAG + event-store schema |
| Event storage exclusive DB | Dedicated event-store database isolated from API query persistence | Compose DB service + Terraform roles + migrations |
| Bronze->silver->gold sequential orchestration | Event-driven Airflow DAG chain triggered from bronze-ready events | Airflow DAG + Redpanda topics |
| EventBridge-like trigger chaining | MinIO notifications and stage-completion events route through Redpanda topics | Terraform bucket notification config + Compose Kafka target wiring + Terraform ACL config |
| Event-first run initiation | Trigger events are emitted first, then `pipeline_run` records are created from those trigger events | Event contracts + event-store schema + pipeline writers |
| Independent source pipelines | Excel, CDC, and Salesforce ingestion runs are tracked independently by `pipeline_name` and trigger criteria | Event-store schema + orchestration contracts |
| Curated boundary after bronze | Curated promotion starts only from bronze-ready events and runs as a separate pipeline domain | Airflow DAG chain + event contracts + event-store lineage fields |
| Partitioning across event storage layers | Redpanda topics are provisioned with canonical partition counts, event-store uses monthly partitions managed by pg_partman/pg_cron, and MinIO writer policies enforce source/date/run_id path templates | Terraform identity topic bootstrap + ACL config, SQL migrations (`partman.create_parent` + `event_store.run_partman_maintenance` + cron schedule), Terraform MinIO IAM policy constraints |
| Encryption with KMS-like controls | MinIO SSE-KMS through KES/Vault with encrypted-write enforcement on `bronze/silver/gold/quarantine` and `landing/raw` excluded in this phase | Terraform bucket policies + KES/Vault config |
| Append-only and replay-first processing | Immutable event log, offset checkpoints, replay-driven backfills | Event-store schema + topic retention policy IaC |
| No destructive data correction | Corrections append new events rather than update/delete history | SQL role constraints + pipeline contract |
| UI shows pipeline status and traceability | Read-only FastAPI query API serving run timeline, lineage, artifacts, alerts | Backend query API + read-model builders |
| UI can generate success/failure demo data | UI triggers source-adapter generators that publish into source ingress paths; Excel generator picks a random actor from Keycloak `finance` role users | Compose source-adapter services + topic contracts + Keycloak IaC |
| Notifications visible to any viewer | UI alert feed populated from `ui.alert.raised.v1` and event-store read models | Event contracts + query API |
| API not required for ETL execution | All ingestion and transformation flows run through source triggers, broker, workers, and Airflow | Architecture boundary + runtime topology |
