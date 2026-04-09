# Terraform Provisioning

Terraform is split into two root configurations with separate state:

- `bootstrap/`: Postgres runtime roles, Keycloak DB schema ownership, MinIO bucket/users/policies
- `identity/`: Keycloak realm, clients, roles, users, and role bindings

This split prevents a startup loop where Keycloak needs DB credentials/schema before it can start, while Terraform Keycloak resources require a running Keycloak API.

The service lifecycle (container start/stop) remains managed by Docker Compose.

## Workflow

Use Make targets from repository root:

```bash
make infra-tf-init
make infra-pg-up
make infra-tf-bootstrap
make infra-kc-up
make infra-tf-apply
```

Staged provisioning flow:

1. `make infra-tf-init`
2. `make infra-pg-up`
3. `make infra-tf-bootstrap`
4. `make infra-kc-up`
5. `make infra-tf-apply`

## Planning and Apply Targets

```bash
make terraform-plan
make terraform-plan-bootstrap
make terraform-plan-identity
make infra-tf-bootstrap
make infra-tf-apply
```

## Notes

- Terraform must be installed locally.
- Terraform values are injected via Make-exported `TF_VAR_*` from `infra/.env`.
- Run Terraform through Make targets so the expected `TF_VAR_*` environment is set.
- State is now stored separately under `infra/terraform/bootstrap` and `infra/terraform/identity`.
- Run `make infra-clean` once after pulling this split so state paths are recreated cleanly.
- Keep real secrets out of git.
