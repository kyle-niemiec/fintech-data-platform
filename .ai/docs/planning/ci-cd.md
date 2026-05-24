# CI/CD (Free-First Hosted Demo)

This specification defines the long-term CI/CD target for Meridian's hosted demo
environment while keeping strict `$0` operating posture as the default.

## Goals and Constraints

- Keep the project fully usable as a portfolio-quality, full-stack event-driven
  architecture without introducing paid-only infrastructure requirements.
- Prefer one EC2 host for operational simplicity; split into multiple hosts only
  when objective capacity gates are breached.
- Keep public ingress limited to UI and read-only API on
  `meridian.codeflower.io`.
- Keep admin and tooling UIs private-only; browser access is through short-lived
  SSM tunnels.
- If a capability cannot stay free, reduce complexity before adding paid
  services.

## Release Interface

- Release tags are semantic version tags: `vMAJOR.MINOR.PATCH`.
- The release workflow is tag-driven only. Pull requests and `main` merges do
  not auto-deploy.

## CI Contract (Pull Requests)

CI runs on GitHub-hosted Actions for all pull requests and blocks merge on any
failed required check.

Required PR checks:
- Python test suite including integration markers used by this repo's CI
  contract.
- UI `typecheck` and UI production build.
- Workflow failure on first failed gate; no partial-success merge path.

The repository remains public to preserve GitHub-hosted Actions free-usage
posture for public repositories.

## CD Contract (Release Tags)

Pushing a semantic tag (`v*`) triggers one deployment workflow with explicit
failure stops:

1. Validate tag format and repo state.
2. Run CI-equivalent validation gates for the tagged commit.
3. Authenticate to AWS via GitHub OIDC role assumption.
4. Run Terraform apply (`bootstrap`, then `identity`) for hosted environment.
5. Connect to EC2 host, pull tagged source, build images in place, and run the
   compose deployment sequence.
6. Run post-deploy health checks and publish deployment status.

If any step fails, later steps do not run.

## Artifact Flow

- No registry dependency is required for the baseline path.
- The EC2 host pulls the tagged repo revision and builds service images in
  place via existing Dockerfiles and compose definitions.
- This keeps infrastructure free-first and avoids additional registry
  authentication/cost complexity.

## Hosted Topology Model

### Primary Topology (Default)

- One EC2 instance runs the full compose-defined platform.
- Public-facing components:
  - `ui` on `443` (reverse-proxied from container)
  - `api` on `443` path or dedicated host route
- No admin tooling endpoints are directly internet-exposed.

### Split-Ready Topology (Only If Capacity Gates Trigger)

If objective thresholds are exceeded, split by container group while preserving
service boundaries and init ordering:

- `edge`
  - `ui`, `api`
- `core-state`
  - `postgres`, `event_store_db`, `minio`, `redpanda`, `vault`, `kes`,
    `keycloak`, `oltp_db`
- `compute-orchestration`
  - Airflow services, `trino`, `iceberg_rest`, source workers, bronze writers,
    `salesforce_mock`, `debezium_server`, `fraud_worker`, `oltp_load_generator`

Current compose/runtime assumes single-host DNS names for internal service
addressing (for example `redpanda`, `minio`, `event_store_db`, `postgres`,
`keycloak`, `airflow_api_server`, `trino`, `iceberg_rest`, `oltp_db`). Any
multi-host split requires explicit endpoint abstraction before cutover.

## Init and Runtime Lifecycle Contract

One-shot initialization jobs are required deployment behavior:
- `vault_bootstrap`
- `kes_bootstrap`
- `airflow_init`
- `trino_curated_init`
- Terraform `bootstrap` apply
- Terraform `identity` apply

Hosted startup sequencing contract:
1. Start foundational runtime dependencies.
2. Apply Terraform `bootstrap`.
3. Start Keycloak.
4. Apply Terraform `identity`.
5. Run one-shot init containers to completion.
6. Start long-running orchestration, worker, API, and UI services.
7. Pass health-gate checks before declaring environment ready.

## Security and Access Story

- Public ports: `80/443` only.
- No public admin ports for Airflow, MinIO Console, pgAdmin, or Keycloak admin
  UI.
- Operators assume an AWS ops role and open short-lived local tunnels with SSM
  Session Manager for browser-based admin access.
- Secrets model:
  - GitHub Actions uses OIDC role assumption (no long-lived AWS keys in GitHub).
  - Runtime and deployment secrets are sourced from AWS SSM Parameter Store
    and/or AWS Secrets Manager.

## Capacity Gate and Split Trigger

Observed full-stack memory baseline during local full bring-up:
- `~6.96 GiB` container RAM footprint (one-sample operational baseline).

Capacity gate policy:
- Stay single-host while steady-state memory, CPU, and restart behavior remain
  within the host budget with operating headroom.
- Trigger split planning when one or more conditions occur:
  - Sustained memory pressure above 85% of host RAM during normal demo load.
  - OOM kills or repeated restart loops in required core services.
  - Inability to complete full-stack health-gated startup reliably.

When triggered, use the split-ready groups above and preserve the init sequence
contract before promoting the new topology.

## Acceptance Checks

### CI/CD Workflow Checks

- PR workflow executes required checks and blocks merge on any failure.
- Tag workflow runs Terraform apply and deploy steps in the defined order with
  explicit stop-on-failure behavior.

### Topology and Access Checks

- Single-host bring-up completes, including one-shot init jobs.
- Public scan confirms only UI/API ingress.
- SSM tunnel runbook provides browser access to private admin UIs without
  public admin ports.

### Split-Readiness Checks

- Hardcoded single-host service endpoint assumptions are documented.
- Split-group plan retains required dependency and init ordering.

## Assumptions and Defaults

- Repository remains public and uses GitHub-hosted runners.
- Strict `$0` policy remains the governing default.
- Single EC2 host remains the default target until capacity gates require
  split.
- EC2 free-tier eligibility and duration depend on AWS account status and must
  be validated at release time.
- Docker Compose remains the hosted deployment orchestrator for this project.

## References

- AWS EC2 Free Tier usage: <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html>
- AWS T3 instance family reference: <https://aws.amazon.com/ec2/instance-types/t3/>
- GitHub plans and Actions billing behavior: <https://docs.github.com/en/get-started/learning-about-github/githubs-plans>
- Docker Compose usage model: <https://docs.docker.com/compose/intro/features-uses/>
- Docker Compose networking: <https://docs.docker.com/compose/how-tos/networking/>
