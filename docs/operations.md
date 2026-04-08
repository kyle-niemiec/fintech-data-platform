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

**`infra/.env`** — Postgres superuser, runtime DB users, and MinIO credentials for Docker Compose:
```
POSTGRES_DB=fintech_platform
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

POSTGRES_ROOT_USER=<choose a superuser name, e.g. fintech_admin>
POSTGRES_ROOT_PASSWORD=<choose a password>

OPERATOR_DB_USER=api_runtime
OPERATOR_DB_PASSWORD=<choose a password>

OBSERVER_DB_USER=audit_runtime
OBSERVER_DB_PASSWORD=<choose a password>

MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=<choose a password>
```

`POSTGRES_ROOT_USER`/`POSTGRES_ROOT_PASSWORD` initialize the Docker Postgres superuser on first run and are used by `make db-psql`. These are separate from the NOLOGIN `db_migrator` role template in `04_create_roles.sql`.

`OPERATOR_DB_USER`/`OPERATOR_DB_PASSWORD` and `OBSERVER_DB_USER`/`OBSERVER_DB_PASSWORD` are the runtime login roles used by the API. They are created automatically on first container initialization by `05_create_login_roles.sql` — no manual SQL required.

`POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`, `OPERATOR_DB_USER`, `OPERATOR_DB_PASSWORD`, `OBSERVER_DB_USER`, and `OBSERVER_DB_PASSWORD` are all exported by the Makefile from `infra/.env` to the backend process — do not define them in `backend/.env`.

**`backend/.env`** — API-only secrets (JWT and credential config only):
```
SECRET_KEY=<32-char random string — generate with: python -c "import secrets; print(secrets.token_hex(32))">

OPERATOR_PASSWORD=<API password for operator identity>
OBSERVER_PASSWORD=<API password for observer identity>
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

Postgres runs on `localhost:5432`. MinIO runs on `localhost:9000` (API) and `localhost:9001` (console).

### 4. Install API dependencies

```bash
make api-install
```

### 5. Run the API

```bash
make api-dev
```

The API runs at `http://127.0.0.1:8000`.

## Makefile Targets

| Target | Description |
| --- | --- |
| `make infra-up` | Start Postgres and MinIO in the background |
| `make infra-down` | Stop infrastructure containers |
| `make infra-ps` | Show infrastructure container status |
| `make api-install` | Install backend Python dependencies into `backend/.venv` |
| `make api-dev` | Run the FastAPI app with reload enabled |
| `make db-psql` | Open a psql shell inside the Postgres container |

## Common Operations

**Restart infrastructure:**
```bash
make infra-down && make infra-up
```

**Check container logs:**
```bash
docker compose -f infra/docker-compose.yaml logs postgres
docker compose -f infra/docker-compose.yaml logs minio
```

**Access MinIO console:**
Open `http://127.0.0.1:9001` in a browser and log in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from `infra/.env`.

