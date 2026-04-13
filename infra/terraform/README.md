# Terraform Provisioning

Terraform is the security and identity control surface for the event-driven platform.

## IaC Responsibility

Terraform owns:
- Object storage policies and service identities.
- Event backbone ACLs and service principals.
- Encryption policy posture (including SSE-KMS requirements).
- Database role grants for append-only event persistence and read-only query access.
- Keycloak realm/client/persona seeding for internal demo actor identity.

Docker Compose owns runtime lifecycle (container start/stop).

## Root Configuration Intent

The platform uses phased Terraform roots to avoid dependency loops and keep concerns isolated.

- `bootstrap/`: foundational storage, DB users/roles, service policies.
- `identity/`: Keycloak realm/client/role/demo-user provisioning.
- `eventing/` (target): broker ACLs, topic bootstrap, service credentials.
- `security/` (target): encryption policy enforcement, KMS/KES policy bindings.

## Provisioning Sequence

1. Start foundational runtime dependencies (Postgres/Event DB/MinIO/Redpanda).
2. Apply bootstrap Terraform for base security primitives.
3. Start Keycloak and apply identity Terraform.
4. Apply eventing/security Terraform roots.
5. Start orchestration and workers (Airflow, scanner, Debezium, fraud, writers).

## Workflow Commands

Use repository Make targets for initialization and apply where available:

```bash
make infra-tf-init
make infra-tf-bootstrap
make infra-tf-apply
make terraform-plan
```

If additional Terraform roots are introduced, extend Make targets and `infra/make/terraform-env.mk` accordingly so all required `TF_VAR_*` inputs are exported consistently.

## Operating Rules

- Keep secrets out of version control.
- Use least-privilege defaults for every new principal.
- Treat policy changes as first-class code review items.
- Require explicit migration notes for any privilege expansion.
