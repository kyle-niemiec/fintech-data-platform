# Operations

## Prerequisites

- Docker + Docker Compose
- Python 3.12+
- GNU Make
- `jq` (optional, for formatted API output)

## Initial Setup

### 1. Configure environment files

```bash
cp infra/.env.example infra/.env
cp backend/.env.example backend/.env
```

**`infra/.env`** — Postgres superuser, runtime DB users, Keycloak DB/admin users, and MinIO credentials:

```env
POSTGRES_DB=fintech_platform
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

POSTGRES_ROOT_USER=<choose a superuser name>
POSTGRES_ROOT_PASSWORD=<choose a password>

OPERATOR_DB_USER=api_runtime
OPERATOR_DB_PASSWORD=<choose a password>

OBSERVER_DB_USER=audit_runtime
OBSERVER_DB_PASSWORD=<choose a password>

PIPELINE_DB_USER=api_pipeline
PIPELINE_DB_PASSWORD=<choose a password>

KC_DB_USER=keycloak_runtime
KC_DB_PASSWORD=<choose a password>
KC_ADMIN_USER=admin
KC_ADMIN_PASSWORD=<choose a password>

MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=<choose a password>
```

`POSTGRES_ROOT_USER`/`POSTGRES_ROOT_PASSWORD` initialize the Docker Postgres superuser on first run and are used by `make db-psql`.

DB login roles (`OPERATOR_DB_USER`, `OBSERVER_DB_USER`, `PIPELINE_DB_USER`) and the Keycloak schema owner (`KC_DB_USER`) are created automatically on first container initialization by `05_create_login_roles.sql`.

All DB connection variables are exported by the Makefile from `infra/.env` when you run `make api-dev`.

**`backend/.env`** — API Keycloak settings:

```env
KEYCLOAK_URL=http://localhost:8180
KEYCLOAK_REALM=meridian
KEYCLOAK_API_CLIENT_ID=meridian-api
KEYCLOAK_API_AUDIENCE=meridian-api
KEYCLOAK_SWAGGER_CLIENT_ID=meridian-api
```

### 2. Create the backend virtual environment (first time only)

```bash
python3 -m venv backend/.venv
```

### 3. Start infrastructure

```bash
make infra-up
make infra-ps
```

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
  -d "client_secret=pipeline-dev-secret" | jq -r .access_token)
```

### Protected endpoint call

```bash
curl -s http://127.0.0.1:8000/runs/ -H "Authorization: Bearer $TOKEN" | jq
```

### Swagger auth flow (operator/observer)

1. Open `http://127.0.0.1:8000/docs`
2. Click **Authorize**
3. Log in via Keycloak (`operator` / `observer`)

## Makefile Targets

| Target | Description |
| --- | --- |
| `make infra-up` | Start Postgres, MinIO, and Keycloak in the background |
| `make infra-down` | Stop infrastructure containers |
| `make infra-ps` | Show infrastructure container status |
| `make infra-clean` | Stop containers and remove local Postgres/MinIO volumes |
| `make api-install` | Install backend Python dependencies into `backend/.venv` |
| `make api-dev` | Run the FastAPI app with reload enabled |
| `make db-psql` | Open a psql shell inside the Postgres container |

## Common Operations

**Restart infrastructure:**

```bash
make infra-down && make infra-up
```

**Reset local infra state:**

```bash
make infra-clean
make infra-up
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
