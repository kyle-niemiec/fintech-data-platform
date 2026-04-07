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

**`infra/.env`** — Postgres and MinIO credentials for Docker Compose:
```
POSTGRES_DB=fintech_platform
POSTGRES_USER=fintech_user
POSTGRES_PASSWORD=<choose a password>
MINIO_ROOT_USER=minio_admin
MINIO_ROOT_PASSWORD=<choose a password>
```

**`backend/.env`** — API runtime credentials:
```
POSTGRES_DB=fintech_platform
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

OPERATOR_DB_USER=api_runtime
OPERATOR_DB_PASSWORD=<password for api_runtime DB user>

OBSERVER_DB_USER=audit_runtime
OBSERVER_DB_PASSWORD=<password for audit_runtime DB user>

SECRET_KEY=<32-char random string — generate with: python -c "import secrets; print(secrets.token_hex(32))">

OPERATOR_PASSWORD=<API password for operator identity>
OBSERVER_PASSWORD=<API password for observer identity>
```

Note: `POSTGRES_DB`, `POSTGRES_HOST`, and `POSTGRES_PORT` in `backend/.env` refer to the Postgres instance started by Docker Compose. `OPERATOR_DB_USER`/`OBSERVER_DB_USER` are runtime login roles that must be created manually (see below).

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

### 5. Create DB runtime login users

The DB migration (`04_create_roles.sql`) creates `NOLOGIN` role templates. You must create the login users manually and bind them to those roles:

```bash
make db-psql
```

Inside the psql shell:

```sql
CREATE ROLE api_runtime LOGIN PASSWORD '<OPERATOR_DB_PASSWORD from backend/.env>';
GRANT control_plane_writer TO api_runtime;

CREATE ROLE audit_runtime LOGIN PASSWORD '<OBSERVER_DB_PASSWORD from backend/.env>';
GRANT control_plane_reader TO audit_runtime;
```

Verify with `\du`.

### 6. Apply security role migration on existing DB volumes

If your Postgres volume was initialized before `04_create_roles.sql` was added, it will not have run automatically. Apply it manually:

```sql
\i /docker-entrypoint-initdb.d/04_create_roles.sql
```

### 7. Run the API

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
