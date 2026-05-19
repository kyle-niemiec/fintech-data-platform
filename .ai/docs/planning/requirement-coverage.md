# Requirement Coverage Matrix

This matrix maps historical requirements from `.ai/docs/00-human-descriptions.md` to local event-driven components, IaC ownership, and delivery status.

| Requirement Theme | Local Implementation | IaC Owner | Delivery Phase |
| --- | --- | --- | --- |
| Excel upload triggers ingestion | Finance upload to MinIO `landing/source=excel/`; object-created notification publishes `ingest.excel.uploaded.v1` to Redpanda | Terraform bootstrap (bucket notification + IAM), Compose (MinIO + Redpanda) | Phase 3 complete |
| Virus, type, and size checks | `excel_scanner` worker enforces ClamAV + MIME + size gates and emits pass/fail events | Compose service + Terraform identity ACLs | Phase 3 complete |
| Airflow-driven schema validation | `excel_validation_trigger` worker consumes scan-pass and triggers Airflow `excel_validation` DAG idempotently | Compose + Terraform identity ACLs | Phase 3 complete |
| Quarantine on validation fail | Airflow DAG copies artifact to `quarantine/` and emits `ingest.excel.quarantined.v1` | Airflow DAG + Terraform MinIO policy | Phase 3 complete |
| Raw-ready on validation pass | Airflow DAG copies artifact to `raw/` and emits `ingest.excel.raw.ready.v1` | Airflow DAG + Terraform MinIO policy | Phase 3 complete |
| Bronze conversion from valid Excel | `excel_bronze_writer` consumes `raw.ready`, writes Parquet to bronze with SSE-KMS, emits `ingest.excel.bronze.ready.v1` | Compose runtime + Terraform MinIO policy + Redpanda ACLs | Phase 3 complete |
| Raw/bronze artifact traceability | `event_store.pipeline_run` + `event_store.event_log` persist run/event lineage with `input_uris[]` and `output_uris[]` | SQL migrations + Terraform DB roles | Phase 3 complete |
| Event storage exclusive DB | Dedicated event-store Postgres instance, isolated from core app DB | Compose + Terraform bootstrap + migrations | Phase 1 complete |
| Event-first run initiation | Trigger event is emitted first; `pipeline_run` enforced to include event before commit | Event contracts + DB trigger constraint | Phase 1 complete |
| Independent ingestion pipelines | Fixed run domains (`excel_ingestion`, `cdc_ingestion`, `salesforce_ingestion`) and curated boundary contract | Event contracts + DB constraints | Phase 1 complete |
| Curated boundary after bronze | Curated run contract begins from `*.bronze.ready.v1` with `parent_run_id` linkage | Event contracts + DB constraints | Phase 1 complete |
| Partitioning across event storage layers | Redpanda topic partition defaults + event-store monthly partitions via `pg_partman/pg_cron` + MinIO path templates | Terraform identity + SQL migrations + Terraform MinIO IAM | Phase 1 complete |
| Encryption with KMS-like controls | MinIO SSE-KMS via KES + Vault Transit; enforced writes on `bronze/silver/gold/quarantine` | Compose (Vault/KES/MinIO) + Terraform bootstrap policy | Phase 2 complete |
| Append-only and replay-first processing | Event-store appender/query role split; append-only grants for runtime writers | SQL hardening migration + Terraform bootstrap roles | Phase 2 complete |
| No destructive data correction | Runtime roles have no `UPDATE`/`DELETE`; replay appends events | SQL hardening migration + role model | Phase 2 complete |
| API is not ETL control plane | FastAPI remains query-only; ingestion flow runs without API availability | Backend boundary + runtime topology | Phase 1 complete |
| CDC via Debezium + fraud path | OLTP Postgres + Debezium Server -> `fraud_worker` (versioned rules, idempotent `risk_flag` upsert) -> `cdc_bronze_writer` (LSN-sorted Parquet + `cdc_checkpoint`) | Compose services + Terraform identity ACLs + OLTP/event-store migrations | Phase 4 complete |
| Salesforce incremental pull path | Airflow scheduled pull -> raw artifact -> bronze-ready events | Planned DAG/services + Terraform secrets/ACLs | Phase 5 planned |
| Curated bronze->silver->gold orchestration | Event-driven DAG chain from bronze-ready into silver and gold outcomes across Salesforce + CDC + Excel curated paths, with listener/transform DAG pairs and checkpoint+event recorded in a single event-store transaction | Compose (Trino + iceberg-rest) + Airflow DAG code + Terraform identity ACLs + event-store migration | Phase 6 complete |
| SCD2 silver dimension + KPI gold | Config-driven `silver_curated_promotion` routes by source/object/table into `dim_opportunity`, `dim_account`, `dim_loan`, `fact_loan_payment`, `loan_status_history`, `fact_commission_adjustment`; config-driven `gold_curated_aggregation` materializes `kpi_pipeline_conversion`, `kpi_portfolio_health`, `kpi_payment_performance`, `kpi_commission_economics`; `masking` provides deterministic AccountId tokenization for stable SCD2 keys; `silver_checkpoint`/`gold_checkpoint` persist merge + record counts | Airflow DAGs + SQL task modules + lakehouse migrations + `masking` lib + event-store migration `05_curated_checkpoints.sql` | Phase 6 complete |
| UI traceability + alert feed | Read-only UI query API uses event-store timeline and alert events | Backend query API + contracts | Phase 7 planned |
| UI-triggered demo data generation | UI triggers internal source adapters (no direct ETL writes via API) | Planned adapter services + Keycloak IaC + contracts | Phase 7 planned |
