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

Terraform receives values through Make-exported `TF_VAR_*` variables sourced from `infra/.env`.

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
make infra-tf-apply
make infra-ps
```

Infrastructure startup is manual and staged:

1. `make infra-tf-init` initializes Terraform providers
2. `make infra-pg-up` starts Postgres + MinIO
3. `make infra-tf-bootstrap` applies bootstrap Terraform (Postgres + MinIO resources, including Keycloak DB prerequisites)
4. `make infra-kc-up` starts Keycloak
5. `make infra-tf-apply` applies identity Terraform (Keycloak realm/clients/roles/users)

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

**Check container logs:**

```bash
docker compose -f infra/docker-compose.yaml logs postgres
docker compose -f infra/docker-compose.yaml logs minio
docker compose -f infra/docker-compose.yaml logs keycloak
```

**Access admin UIs:**

- Keycloak Admin: `http://localhost:8180`
- MinIO Console: `http://127.0.0.1:9001`

## Notes

- Docker Compose treats `$` as interpolation. If a secret in `infra/.env` contains `$`, escape it as `$$` (for example, `abc$$u`).
- Terraform is now split across `infra/terraform/bootstrap` and `infra/terraform/identity` with separate state files. Run `make infra-clean` once after pulling this refactor so state paths are recreated cleanly.
