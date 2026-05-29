<div align="center">
  <img src=".github/assets/meridian-banner.svg" alt="Meridian" width="600"/>
</div>

<br />

> A personal note: This is an ongoing project that I undertook following my IBM data engineering certification course. I felt that I needed a place to exercise the combination of skills and technologies that I had learned about, as well as a place to practice working within industry-standard configurations. From a job posting I aspired to qualify for was born Meridian: the business story behind an ETL platform for 3 disparate sources of data. The project is still a work-in-progress, but I hope that it demonstrates some of my thought process as an engineer.
>
> If you would like to take a look at the application in action, just visit the deployment at <a href="https://meridian.codeflower.io/" target="_blank">meridian.codeflower.io</a>. Thanks for coming to take a look!
>
> — Kyle

## Welcome to Meridian

**Meridian Wealth Management** is a mid-sized wealth-management firm. We run four interlocking business lines: the **Trading Desk** executes orders against client accounts, the **lending book** extends credit against client portfolios, **Sales** maintains the client relationship through a CRM, and behind both, **People Operations** runs payroll while **Revenue Operations** reconciles advisor commissions. Each business line produces data in a different shape, from a different system, on a different schedule.

In a regulated firm, those four streams are not allowed to drift apart. Every trade, every commission adjustment, every client opportunity has to reconcile into the same firm-wide picture: regulators expect us to account for it byte by byte. Our compliance posture is anchored in **FINRA** and **SOC 2**, with **GDPR**-style data-subject handling as a stretch objective; that posture makes accountability an operating requirement rather than an aspiration. The hardest part of the job is not the size of the data — it is the discipline of treating every record as defensible.

The Meridian data platform is the connective tissue that lets every team trust the same numbers. It ingests each source on its own terms, cleans and normalizes the result into a tiered lakehouse, and preserves a complete audit trail so any number on a leadership dashboard can be traced back to the run that produced it. The principle is simple to state and unforgiving to enforce: **every record has to be accountable**.

For the full portrait of Meridian as a firm — departments, workflows, regulatory frame — see [`.ai/docs/meridian-lore.md`](.ai/docs/meridian-lore.md).

## Try it

Open **<a href="https://meridian.codeflower.io/" target="_blank">meridian.codeflower.io</a>** and drive each pipeline from the console:

- **Generate a transaction** to watch the fraud model score it in real time; a high-value NVDA trade trips a high-severity alert within seconds.
- **Upload a payroll workbook** to walk a clean file through scan, validate, and promotion to bronze; choose the invalid variant to watch the quarantine guardrail catch a missing column.
- **Replay a backfill** to see a historical period re-processed end to end without ever rewriting history.
- **Trigger a customer erasure** to confirm that a subject can be forgotten from silver and gold while bronze retention stays intact.

Everything you see is reconstructed live from the event store — no screenshots, no static fixtures.

## How Meridian ships

The release path is small, conventional, and entirely AWS-native. A semantic version tag pushed to this repository triggers a **GitHub Actions** workflow. The workflow assumes a least-privileged **IAM** role through OIDC trust, so no long-lived AWS keys live in CI.

The hosted demo stack (landing page, control-plane API, scheduled stop, distribution) is defined in **CloudFormation** and provisioned once. From there, every release moves through **SSM Run Command**, which pushes the new image set onto a single **EC2** instance running the Docker Compose stack; the previous release tag is captured in **SSM Parameter Store** alongside the current one, so a one-command rollback to the last good version is always available.

Public traffic enters through **CloudFront**, which terminates TLS using a certificate from **ACM** and is resolved via **Route 53**. When the demo instance is asleep, the same distribution falls back to a static launcher page hosted in **S3** — visitors see a "click to wake" experience instead of a connection error. The launcher itself runs as two **Lambda** functions (start-demo and stop-demo), and **EventBridge Scheduler** fires the stop function once the session's TTL expires, returning the instance to sleep without manual intervention.

That is the entire deployment surface: ten AWS services, one CI workflow, one tagged commit per release.

## Tech stack

| Component | Role |
| --- | --- |
| **Redpanda** | Kafka-API event backbone: durable topics, replay, fan-out |
| **Apache Airflow** | Event-triggered DAG orchestration for validation and curated transforms |
| **MinIO** | S3-compatible lakehouse object storage |
| **Trino + Apache Iceberg** | Curated query engine and table format (SCD2, time travel) |
| **Debezium** | Change-data-capture from the trading OLTP database |
| **HashiCorp Vault + KES** | KMS for MinIO server-side encryption |
| **Keycloak** | OIDC identity for demo personas |
| **ClamAV** | Upload malware scanning |
| **PostgreSQL** | Event store, trading OLTP source, and platform catalog database |
| **FastAPI** | Read-only query API |
| **React + Vite** | Demo console |
| **Terraform + Docker Compose** | Infrastructure as code for the local stack |

## Running locally

**Prerequisites:** Docker, Docker Compose, GNU Make. Terraform runs inside a container; no host install required.

```bash
cp infra/.env.example infra/.env   # fill in secrets
make infra-up-dev                  # staged bring-up
```

When the stack settles, access the app from:

- UI: http://localhost:3000
- API: http://localhost:8000

## Where to learn more

- [`.ai/docs/meridian-lore.md`](.ai/docs/meridian-lore.md): the full business portrait of Meridian — departments, business lines, regulatory frame, operational stories.
- [`.ai/docs/planning/`](.ai/docs/planning/): architecture, event contracts, source-pipeline details, security and access maps, operations playbooks.

Deeper technical references (pipeline internals, compliance mechanics, end-to-end test plans) will land in a top-level `docs/` folder as the project's external surface grows.

## Built with AI assistance

This project was built collaboratively with an AI coding agent under a disciplined per-task development loop: load project context, reconcile with the plan, make the minimal change, verify, update the tracking, report deltas. Every deferred shortcut was tagged in code and tracked in a ledger, and removed together when the debt was paid. The discipline shows up in the codebase as traceable decisions; the same accountability the platform provides for Meridian's data, applied to its own construction.
