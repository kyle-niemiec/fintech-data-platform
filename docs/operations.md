# Operations

## Prerequisites

- Docker + Docker Compose
- Terraform 1.6+
- Python 3.12+
- GNU Make
- `jq` (optional, for formatted API output)

## Initial Setup

### 1. Configure environment files

```bash
cp infra/.env.example infra/.env
cp backend/.env.example backend/.env
```

`infra/.env` is the single local source of truth for Compose + Terraform + backend runtime exports:

- Postgres superuser and runtime users
- Keycloak DB/admin credentials, realm/client settings, seeded local users
- MinIO root credentials, bucket name, IAM user secrets

Terraform receives values through Make-exported `TF_VAR_*` variables sourced from `infra/.env` via [infra/make/terraform-env.mk](../infra/make/terraform-env.mk).

`backend/.env` ships with placeholder values. Fill it in so that the Keycloak realm, client IDs, and audience match what the identity Terraform provisions — by default that means `KEYCLOAK_REALM=meridian`, `KEYCLOAK_API_CLIENT_ID=meridian-api`, `KEYCLOAK_API_AUDIENCE=meridian-api`, and `KEYCLOAK_SWAGGER_CLIENT_ID=meridian-api`. The `KEYCLOAK_URL` should match what Compose exposes (default `http://localhost:8180`).

### 2. Create the backend virtual environment (first time only)

```bash
python3 -m venv backend/.venv
```

### 3. Start and provision infrastructure

```bash
make infra-tf-init
make infra-pg-up
make infra-tf-bootstrap
make infra-kc-up
# wait for Keycloak readiness (see step 4 notes below)
make infra-tf-apply
```

Infrastructure startup is manual and staged:

1. `make infra-tf-init` initializes Terraform providers for both bootstrap and identity.
2. `make infra-pg-up` starts Postgres + MinIO. DB migrations under [infra/db/migrations/](../infra/db/migrations/) auto-apply via the Postgres container's `docker-entrypoint-initdb.d` mount on first boot.
3. `make infra-tf-bootstrap` applies bootstrap Terraform: Postgres runtime login users bound to the migration-defined role templates, the `keycloak_runtime` login + `keycloak` schema that Keycloak needs to start, and the MinIO bucket/users/policies.
4. `make infra-kc-up` starts Keycloak (which uses the `keycloak_runtime` Postgres user and `keycloak` schema provisioned in step 3). Wait until Keycloak is fully ready before continuing (for example, container state is `Up` and logs include `Listening on: http://0.0.0.0:8080`).
5. `make infra-tf-apply` applies identity Terraform: realm, clients (`meridian-api`, `meridian-pipeline`), roles, and seeded users.

The split exists because Keycloak needs DB credentials to start, but the identity Terraform needs a running Keycloak API to talk to. See [infra/terraform/README.md](../infra/terraform/README.md) for the workflow reference.

Infrastructure services:

- Postgres: `localhost:5432`
- MinIO API: `localhost:9000`
- MinIO Console: `localhost:9001`
- Keycloak: `localhost:8180`

### 4. Install API dependencies

```bash
make api-install
```

### 5. Run the API

```bash
make api-dev
```

The API runs at `http://127.0.0.1:8000`.

## Quick Verification

### Pipeline token (client credentials)

```bash
TOKEN=$(curl -s -X POST http://localhost:8180/realms/meridian/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=meridian-pipeline" \
  -d "client_secret=$KC_PIPELINE_CLIENT_SECRET" | jq -r .access_token)
```

### Protected endpoint call

```bash
curl -s http://127.0.0.1:8000/runs/ -H "Authorization: Bearer $TOKEN" | jq
```

### Swagger auth flow (operator/observer)

1. Open `http://127.0.0.1:8000/docs`
2. Click **Authorize**
3. Log in via Keycloak (`KEYCLOAK_OPERATOR_USER` / `KEYCLOAK_OBSERVER_USER`)

## Makefile Targets

| Target | Description |
| --- | --- |
| `make infra-up` | Print the manual staged startup sequence |
| `make infra-tf-init` | Initialize Terraform providers for bootstrap + identity |
| `make infra-pg-up` | Start Postgres + MinIO containers |
| `make infra-tf-bootstrap` | Apply Terraform bootstrap phase (Postgres + MinIO) |
| `make infra-kc-up` | Start Keycloak container |
| `make infra-tf-apply` | Apply Terraform identity phase (Keycloak) |
| `make infra-down` | Stop infrastructure containers |
| `make infra-ps` | Show infrastructure container status |
| `make infra-clean` | Stop containers, remove local volumes, and remove Terraform local state |
| `make terraform-plan` | Show Terraform plan for bootstrap + identity |
| `make api-install` | Install backend Python dependencies into `backend/.venv` |
| `make api-dev` | Run the FastAPI app with reload enabled |
| `make db-psql` | Open a psql shell inside the Postgres container |

## Common Operations

**Restart infrastructure:**

```bash
make infra-down
make infra-tf-init
make infra-pg-up
make infra-tf-bootstrap
make infra-kc-up
make infra-tf-apply
```

**Reset local infra state (clean slate):**

```bash
make infra-clean
make infra-tf-init
make infra-pg-up
make infra-tf-bootstrap
make infra-kc-up
make infra-tf-apply
```

**Check container status:**

```bash
make infra-ps
```

**Check container logs:**

```bash
docker compose -f infra/docker-compose.yaml logs postgres
docker compose -f infra/docker-compose.yaml logs minio
docker compose -f infra/docker-compose.yaml logs keycloak
```

**Access admin UIs:**

- Keycloak Admin: `http://localhost:8180`
- MinIO Console: `http://127.0.0.1:9001`

## Adding a New Infrastructure Secret

When you need a new secret or variable available to Terraform:

1. Add it to [infra/.env.example](../infra/.env.example) (with a placeholder) and to your local `infra/.env` (with the real value).
2. Bridge it to Terraform by adding a `TF_VAR_*` line in [infra/make/terraform-env.mk](../infra/make/terraform-env.mk).
3. Declare a matching `variable` block in the relevant Terraform module (`infra/terraform/bootstrap/variables.tf` or `infra/terraform/identity/variables.tf`) and consume it in provider/resource configuration.
4. Only if the backend runtime also needs this value: add it to backend settings (`backend/.env.example` / `backend/.env`, plus [Makefile](../Makefile) exports if applicable).

Skipping step 2 is the most common mistake — the value exists in `.env`, but Terraform sees it as unset because no `TF_VAR_*` export was emitted.

## Notes

- Docker Compose treats `$` as interpolation. If a secret in `infra/.env` contains `$`, escape it as `$$` (for example, `abc$$u`).
- Terraform state lives separately under `infra/terraform/bootstrap` and `infra/terraform/identity`. Each phase has its own `terraform.tfstate`; `make infra-clean` removes both along with the local Postgres/MinIO volumes.
