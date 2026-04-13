# Terraform Provisioning

Terraform is the security and identity control surface for the event-driven platform.
Terraform runs in Docker (`terraform_runner`) and is not executed from the host OS.

## IaC Responsibility

Terraform owns:
- Object storage policies and service identities.
- Event backbone ACLs and service principals.
- Encryption policy posture (SSE-KMS header enforcement + bucket default encryption).
- Database role grants for append-only event persistence and read-only query access.
- Keycloak realm/client/persona seeding for internal demo actor identity.

Docker Compose owns runtime lifecycle (container start/stop).
Vault/KES runtime startup is Compose-owned; encryption enforcement contracts are Terraform-owned.

## Root Configuration Intent

The platform uses phased Terraform roots to avoid dependency loops and keep concerns isolated.

- `bootstrap/`: foundational storage, DB users/roles, SSE-KMS enforcement policies.
- `identity/`: Keycloak realm/client/role/demo-user provisioning.
- `eventing/` (target): broker ACLs, topic bootstrap, service credentials.

## Provisioning Sequence

1. Start foundational runtime dependencies (Postgres/Event DB/Vault/KES/MinIO/Redpanda).
2. Apply bootstrap Terraform for base security primitives.
3. Start Keycloak and apply identity Terraform.
4. Apply eventing Terraform roots.
5. Start orchestration and workers (Airflow, scanner, Debezium, fraud, writers).

## Workflow Commands

Use repository Make targets for initialization and apply where available:

```bash
make infra-tf-init
make infra-tf-bootstrap
make infra-tf-apply
make terraform-plan
```

These targets invoke `docker compose run --rm terraform_runner ...` and map `.env` values to `TF_VAR_*` inside the runner.

## Connectivity Model

- Terraform provider endpoints use Docker service DNS (`postgres`, `event_store_db`, `minio`, `keycloak`).
- Postgres, event-store Postgres, MinIO, Redpanda, Vault, and KES remain internal-only and are not host-port accessible.
- Host loopback endpoints (`localhost:*`) are not part of the Terraform contract.

## Operating Rules

- Keep secrets out of version control.
- Use least-privilege defaults for every new principal.
- Treat policy changes as first-class code review items.
- Require explicit migration notes for any privilege expansion.
