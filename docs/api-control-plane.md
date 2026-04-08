# Control Plane API

The control plane API is the metadata interface for the data platform. It tracks pipeline runs, artifacts, and lineage — but never holds data payloads directly.

Base URL: `http://127.0.0.1:8000`

Interactive docs: `http://127.0.0.1:8000/docs` (Swagger UI with "Authorize" button)

## Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/token` | None | Issue a JWT for a registered principal |
| `POST` | `/runs/` | operator, pipeline | Create a new ingestion run |
| `GET` | `/runs/` | observer+ | List all runs, newest first |
| `GET` | `/runs/{run_id}` | observer+ | Fetch a single run by UUID |
| `POST` | `/artifacts/` | operator, pipeline | Register an artifact for a run |
| `GET` | `/artifacts/` | observer+ | List artifacts for a run |
| `GET` | `/artifacts/{artifact_id}` | observer+ | Fetch a single artifact |
| `POST` | `/lineage/` | operator, pipeline | Register a lineage relationship |
| `GET` | `/lineage/` | observer+ | List lineage records for a run |

## Authentication

The API uses OAuth2 Password Flow with HS256 JWTs. Credentials are stored in the `principal` table (bcrypt-hashed) and seeded via `make seed-principals`.

**Roles:**

- `operator` — read + write. Can create runs, artifacts, and lineage records. Uses `control_plane_writer` DB session.
- `observer` — read only. Uses `control_plane_reader` DB session.
- `pipeline` — write only (service account). Can create runs, artifacts, and lineage records. Uses `ingestion_writer` DB session.

Adding new roles requires only a row in the `principal` table and a corresponding entry in `ROLE_SESSION_MAP` — no code changes to the auth flow itself.

## Examples

### Get a token

```bash
curl -s -X POST http://127.0.0.1:8000/token \
  -d "username=operator&password=<OPERATOR_PASSWORD>"
```

Response:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

Store the token for subsequent requests:
```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/token \
  -d "username=operator&password=<OPERATOR_PASSWORD>" | jq -r .access_token)
```

### Create a run

```bash
curl -s -X POST http://127.0.0.1:8000/runs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_type": "excel_upload", "triggered_by": "manual_ui"}' | jq
```

Response (201):
```json
{
  "run_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "source_type": "excel_upload",
  "status": "pending",
  "triggered_by": "manual_ui",
  "started_at": "2026-04-07T12:00:00Z",
  "completed_at": null
}
```

### List all runs

```bash
curl -s http://127.0.0.1:8000/runs/ \
  -H "Authorization: Bearer $TOKEN" | jq
```

### Get a single run

```bash
curl -s http://127.0.0.1:8000/runs/<run_id> \
  -H "Authorization: Bearer $TOKEN" | jq
```

Returns 404 if the run does not exist.

### Error responses

| Status | Condition |
| --- | --- |
| 401 | No token provided, token expired, or token invalid |
| 403 | Token valid but role insufficient (e.g. observer calling POST /runs/) |
| 404 | Run ID not found |
| 422 | Request body validation failure |

## UI Access

| Interface | URL |
| --- | --- |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |
| MinIO Console | `http://127.0.0.1:9001` |

The Swagger UI "Authorize" button accepts operator or observer credentials and handles token attachment automatically for in-browser testing.
