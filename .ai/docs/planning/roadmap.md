# Development Roadmap

This roadmap is ordered around event-driven delivery, not API-first delivery.

Terraform work is split into two phases applied via the in-network `terraform_runner` container:
- `bootstrap` - storage and database resources (Postgres roles/databases, MinIO buckets, bucket policies, encryption configuration).
- `identity` - Keycloak realm/clients, Redpanda topic ACLs, and service identities.

## Phase 1 - Event-Driven Foundation

- Redpanda is the canonical broker (compose service on internal network).
- Dedicated event-store database runs as an isolated Postgres instance.
- Internal Docker network boundaries enforced (`platform_internal` is `internal: true`; data-plane services publish no host ports).
- Wire MinIO bucket notifications to Redpanda.
- Define Redpanda topic ACLs and service identities in the Terraform `identity` phase.
- Enforce partitioning standards in active writers/jobs (topic keys, event-store monthly partition automation via pg_partman/pg_cron, object-path partition templates).

## Phase 2 - Encryption and Append-Only Roles

Network isolation is already in place via Phase 1, so this phase focuses on data-at-rest and database authorization controls.

- Enforce MinIO SSE-KMS via KES + Vault Transit.
- Enforce encrypted writes on `bronze/*`, `silver/*`, `gold/*`, and `quarantine/*`.
- Keep `landing/*` and `raw/*` writable without mandatory KMS headers in this phase.
- Define append-only database runtime role permissions for the event-store DB in Terraform `bootstrap` (`event_append_runtime` -> `event_store_appender`).
- Keep query runtime read-only (`event_query_runtime` -> `event_store_reader`).
- Add key/credential rotation runbook guidance for Vault transit keys, MinIO users, and event-store runtime logins.

## Phase 3 - Excel Pipeline

- ClamAV scanner worker consumes `ingest.excel.uploaded.v1` and enforces size/type/malware gates.
- Dedicated trigger worker consumes `ingest.excel.scanned.pass.v1` and creates idempotent Airflow DAG runs (`dag_run_id=excel_validation__<run_id>`).
- Airflow `excel_validation` DAG performs schema validation and emits:
  - `ingest.excel.raw.ready.v1` on pass (`pipeline_run` remains `running`)
  - `ingest.excel.quarantined.v1` on fail (`pipeline_run` closes `quarantined`)
- Dedicated bronze writer consumes `ingest.excel.raw.ready.v1`, writes Parquet to bronze with SSE-KMS headers, emits `ingest.excel.bronze.ready.v1`, and closes run `completed` (or `failed` with alert on error).
- Terraform identity provisions dedicated Redpanda principals for scanner, airflow trigger, and bronze writer with least-privilege topic/group ACLs.
- Terraform bootstrap provisions dedicated MinIO validation principal (`landing/raw/quarantine` scope) used by the Airflow validation DAG.

## Phase 4 - CDC and Fraud Pipeline

- Dedicated OLTP Postgres (`wal_level=logical`) with `trading.transaction` and `trading.risk_flag` schema, per-role credentials (`oltp_app`, `cdc_replicator`, `oltp_ui_reader`), and a `cdc_pub` publication.
- Synthetic load generator seeds transactions on a configurable cadence with varied instrument/amount mixes so continuous scoring behavior is observable in every run.
- Debezium Server (single container, `pgoutput`) streams WAL changes to Redpanda with a `ByLogicalTableRouter` SMT collapsing all `trading.*` tables onto the canonical `cdc.oltp.raw.v1` topic.
- Fraud worker consumes raw CDC events, scores transactions with the demo continuous model (`r(x) = -r_f/(x+r_f)+1`, `r_f(X)=X*(1-r_t)/r_t`, `r_t=0.8`), upserts `trading.risk_flag` idempotently via `(raw_topic, raw_partition, raw_offset)`, and emits `cdc.oltp.assessed.v1`.
- CDC bronze writer batches assessed events, writes zero-transformation Parquet to `bronze/source=cdc/...` with SSE-KMS, emits `cdc.oltp.bronze.ready.v1`, and records a `cdc_checkpoint` row per flush (LSN range + Kafka offsets + record count).
- Event-store DDL adds `event_store.cdc_checkpoint`; `append_cdc_checkpoint` helper joins the existing `event_store.PgEventStore` API.
- Root UI runs view generalized across pipelines with a multi-select pipeline pill filter and a Recent Transactions tab backed by a least-privilege `oltp_ui_reader` role.

## Phase 5 - Salesforce Pipeline

- Add mock Salesforce service and incremental pull logic.
- Implement scheduled incremental pull DAG trigger.
- Persist pull cursor history and raw response artifacts.
- Emit bronze-ready events for CRM objects.

## Phase 6 - Curated Layer Orchestration

Roadmap focus in this phase is the Salesforce Opportunity vertical slice as the first curated path.

- Trino coordinator (single node) with the Iceberg connector backs the curated transform engine; iceberg-rest REST catalog persists Iceberg metadata in a dedicated `iceberg` schema of the platform Postgres; S3 writes go through the existing `MINIO_TRINO_WRITE` identity with SSE-KMS enforced via KES + Vault Transit.
- `lakehouse.silver.dim_opportunity` is an SCD2 Iceberg table at `s3://.../silver/domain=salesforce_opportunity/` partitioned by year/month/day on SystemModstamp. `lakehouse.gold.kpi_pipeline_conversion` is an append-style Iceberg table at `s3://.../gold/metric=pipeline_conversion/` partitioned by snapshot_date.
- Airflow DAG pairs follow a listener/transform split: a `@continuous` listener DAG drives `AwaitMessageTriggerFunctionSensor` and fans out `TriggerDagRunOperator` runs per matching upstream event; the transform DAG is `schedule=None` with `max_active_runs>1` for parallelism.
- `silver_curated_promotion` consumes `ingest.salesforce.bronze.ready.v1`, opens a `curated_promotion` run with `parent_run_id = bronze.run_id`, reads the bronze parquet into a staging parquet on MinIO with AccountId tokenized via the new `masking` library, runs the SCD2 MERGE via Trino, records an `event_store.silver_checkpoint`, emits `pipeline.silver.completed.v1`, and closes the run in a single event-store transaction. Failure emits `pipeline.silver.failed.v1` and closes the run `failed`.
- `gold_curated_aggregation` consumes `pipeline.silver.completed.v1`, opens a `curated_promotion` run with `parent_run_id = silver.run_id`, runs the KPI INSERT via Trino, records an `event_store.gold_checkpoint`, emits `pipeline.gold.completed.v1`, and closes the run in a single event-store transaction.
- Event-store adds `event_store.silver_checkpoint` and `event_store.gold_checkpoint` with FK to `pipeline_run(run_id)` plus `append_silver_checkpoint` / `append_gold_checkpoint` helpers on the existing `event_store.PgEventStore` API.
- `masking` library provides deterministic HMAC-SHA256 masking (`tokenize`, `mask_email`, `hash_pii`, `redact`) with salt sourced from the `PLATFORM_MASKING_SALT` env var; used by the silver DAG and available for future curated transforms.
- Redpanda identity extends the existing `rp_orchestrator_service` principal with READ on `pipeline.silver.completed.v1` and the two new curated consumer groups (`airflow-curated-silver-v1`, `airflow-curated-gold-v1`); `airflow_init` seeds `kafka_default` and `trino_default` Airflow connections idempotently on every bring-up.

Phase 6 follow-on scope is implemented in the same contract family (`pipeline_name=curated_promotion`, existing `pipeline.silver.*.v1` and `pipeline.gold.*.v1` topics) via config-driven transform routing:
- Additional silver entities: `lakehouse.silver.dim_account`, `lakehouse.silver.dim_loan`, `lakehouse.silver.fact_loan_payment`, `lakehouse.silver.loan_status_history`, `lakehouse.silver.fact_commission_adjustment`.
- Additional gold KPIs: `lakehouse.gold.kpi_portfolio_health`, `lakehouse.gold.kpi_payment_performance`, `lakehouse.gold.kpi_commission_economics`.
- Curated source coverage now includes Salesforce (`Account` + `Opportunity`), CDC (`trading.loan`, `trading.loan_payment`, `trading.loan_status_history`), and Excel (`commission_adjustment_v1` schema contract path).

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

## Phase 10 - Free-First CI/CD and Hosted Operations

- Implement three GitHub Actions lanes:
  - `pr-ci.yml` (fast PR gate: Python unit tests excluding `tests/integration`,
    UI typecheck, UI build).
  - `integration-nightly.yml` (daily full-stack integration run against compose).
  - `release-tag-deploy.yml` (semantic tag release guard + integration gate +
    hosted deploy).
- Keep the release trigger interface semantic-tag-only (`vMAJOR.MINOR.PATCH`)
  with an ancestry guard that requires the tagged commit to be reachable from
  `main`.
- Use AWS OIDC role assumption from GitHub Actions and deploy to EC2 via SSM
  Run Command only (no SSH workflow dependency).
- Deploy sequence on EC2 is deterministic and failure-stop:
  - checkout target tag
  - `make infra-clean`
  - generate a new random `infra/.env` (deploy-only rotation)
  - apply hosted domain/UI settings
  - `make infra-up` (includes Terraform bootstrap/identity and required
    init jobs through staged startup)
  - run hosted health checks.
- Persist hosted release state in SSM Parameter Store:
  - `/meridian/demo/current_tag`
  - `/meridian/demo/last_good_tag`
- On deploy failure, attempt automatic rollback by redeploying the prior
  `last_good_tag` through the same SSM deploy path.
- Enforce hosted ingress policy with direct demo-UI exposure:
  - public `443` for UI
  - `/ui/*` routed to API by UI nginx
  - no public admin/service ports.
- Keep split-ready topology groups documented, but retain single-host default
  until objective capacity gates are breached.
- AWS account resources (EC2/IAM/OIDC trust/SG/DNS) are provisioned manually in
  v1 and operated through runbook contracts.

Phase 10 completion criteria:
- Required workflows exist and enforce the defined quality/deploy contracts.
- Hosted deployment and rollback scripts exist and are wired to SSM parameters.
- Hosted compose layering enforces the public/private network boundary.
- Operations runbook includes SSM-only admin access and tag-release flow.

## Phase 11 - Same-Domain Demo Launcher (Scale-to-Zero)

- Add in-repo CloudFormation stack (`infra/cloudformation/demo-launcher.yaml`)
  for launcher infrastructure:
  - CloudFront distribution on `meridian.codeflower.io`.
  - Origin group failover:
    - primary: EC2 app origin DNS (for example `meridian-origin.codeflower.io`)
    - failover: S3 static launcher landing page.
  - Public control Lambda Function URL (no auth in v1) with:
    - `POST /start`
    - `GET /status`
  - Stop Lambda invoked by EventBridge Scheduler one-time schedule.
  - Optional Route53 alias record creation when hosted zone id is provided.
- Keep release contract tag-driven (`vMAJOR.MINOR.PATCH`) and preserve full app
  rebuild on EC2 for every release tag.
- Add conditional launcher-infra release stage:
  - runs after integration gate
  - applies launcher stack only when launcher assets/IaC changed, or when stack
    does not yet exist.
- Keep v1 abuse controls out of scope by design (no captcha/rate limit/WAF in
  this phase).

Phase 11 completion criteria:
- Launcher stack template, Lambda handlers, and static landing assets exist in
  repo.
- Release workflow can conditionally package/deploy launcher infra and sync
  landing assets.
- Same demo domain serves app while EC2 is healthy and launcher page while EC2
  is unavailable.
- Start action from launcher creates a one-time auto-stop window (default
  30 minutes) and repeated starts while running do not extend that window.
- Operations docs define required variables/parameters and known failover
  limitations (including no POST failover).

# Cloud Setup Checklist (Phase 10 v1)

Use this checklist to provision and validate the hosted demo path for
`meridian.codeflower.io`.

Scope: manual AWS provisioning + GitHub workflow wiring for the existing
Phase 10 deployment contract.

## 0) Preconditions

- [✅] Repo is public (required for free-first GitHub Actions posture).
- [✅] You have AWS console access with permission to create EC2, IAM roles,
  security groups, and SSM parameters.
- [✅] Domain control is available for `codeflower.io`.

## 1) Create EC2 Host (Single Instance)

- [ ] Launch one Linux EC2 instance for the demo host.
- [ ] Attach an instance profile/role that allows:
  - SSM core access (Session Manager + Run Command).
  - SSM Parameter Store read/write for:
    - `/meridian/demo/current_tag`
    - `/meridian/demo/last_good_tag`
- [ ] Ensure SSM Agent is active and instance shows as managed in
  AWS Systems Manager.
- [ ] Install runtime prerequisites on host:
  - `git`
  - `docker` + Compose plugin
  - `make`
- [ ] Verify Docker is usable by the deploy user.

## 2) Configure Security Group

- [ ] Inbound: allow `443/tcp` from internet.
- [ ] Inbound: do not expose admin/service ports publicly (`8080`, `8180`,
  `5050`, `9001`, database/broker ports).
- [ ] Outbound: allow required egress for package/image pulls and AWS APIs.

## 3) Configure DNS

- [ ] Create DNS record for `meridian.codeflower.io` pointing to the EC2 public
  endpoint (Elastic IP recommended for stability).
- [ ] Confirm name resolution:
  - `dig meridian.codeflower.io +short`

## 4) Create GitHub OIDC Deploy Role in AWS

- [ ] Create IAM OIDC provider for GitHub Actions (if not already present):
  `token.actions.githubusercontent.com`.
- [ ] Create IAM role trusted by GitHub OIDC for this repo.
- [ ] Trust policy restricts `sub` to your repo (and optionally branch/tag refs).
- [ ] Attach permissions for deployment workflow:
  - SSM Run Command on target instance.
  - SSM command invocation reads.
  - SSM Parameter Store get/put for release state paths.

## 5) Configure GitHub Repo Settings

In `Settings -> Secrets and variables -> Actions`:

- [ ] Add secret:
  - `AWS_ROLE_TO_ASSUME` = IAM role ARN from step 4.
- [ ] Add variables:
  - `AWS_REGION` (for example `us-east-1`)
  - `MERIDIAN_EC2_INSTANCE_ID` (target demo host)
  - `MERIDIAN_HOSTED_DOMAIN` = `meridian.codeflower.io` (optional but recommended)
  - `MERIDIAN_CURRENT_TAG_PARAM` = `/meridian/demo/current_tag` (optional)
  - `MERIDIAN_LAST_GOOD_TAG_PARAM` = `/meridian/demo/last_good_tag` (optional)

## 6) Validate SSM Connectivity Before First Release

- [ ] From your workstation, confirm the instance is managed:
  - `aws ssm describe-instance-information`
- [ ] Smoke-test Run Command:
  - Send `echo ok` to the instance and confirm success.

## 7) First Release Deployment

- [ ] Create semantic tag from a commit reachable by `main`:

```bash
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

- [ ] In GitHub Actions, confirm `release-tag-deploy.yml` passes:
  - semver validation
  - main-ancestry validation
  - integration gate
  - AWS OIDC auth
  - SSM deploy execution

## 8) Post-Deploy Verification

- [ ] Open `https://meridian.codeflower.io` and verify UI loads.
- [ ] Verify API path through UI ingress:
  - `https://meridian.codeflower.io/ui/runs?limit=1`
- [ ] Confirm only intended public port is reachable (`443`).
- [ ] Confirm release state parameters are updated:
  - `/meridian/demo/current_tag`
  - `/meridian/demo/last_good_tag`

## 9) Rollback Readiness Check

- [ ] Confirm a previous successful tag exists in
  `/meridian/demo/last_good_tag`.
- [ ] Confirm failed deploys trigger rollback behavior in workflow logs.

## 10) Operations Model Confirmation

- [ ] Admin UIs are accessed only through short-lived SSM tunnels.
- [ ] No SSH-based deploy path is required.
- [ ] `make infra-up` remains the production startup contract.

## References

- [operations.md](operations.md) (Hosted CI/CD operations section)
- [ci-cd.md](ci-cd.md) (contract and constraints)
- [roadmap.md](roadmap.md) (Phase 10 scope and manual-provisioning status)
