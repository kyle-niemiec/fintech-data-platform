# Control Plane API

The control plane API is the metadata interface for the data platform. It tracks pipeline runs, artifacts, and lineage and does not store payload data.

Base URL: `http://127.0.0.1:8000`

Interactive docs: `http://127.0.0.1:8000/docs` (Swagger UI + Keycloak login)

## Endpoints

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/runs/` | operator, pipeline | Create a new ingestion run |
| `GET` | `/runs/` | observer+ | List all runs, newest first |
| `GET` | `/runs/{run_id}` | observer+ | Fetch a single run by UUID |
| `POST` | `/artifacts/` | operator, pipeline | Register an artifact for a run |
| `GET` | `/artifacts/` | observer+ | List artifacts for a run |
| `GET` | `/artifacts/{artifact_id}` | observer+ | Fetch a single artifact |
| `POST` | `/lineage/` | operator, pipeline | Register a lineage relationship |
| `GET` | `/lineage/` | observer+ | List lineage records for a run |

## Authentication

Authentication is delegated to Keycloak (`meridian` realm).

- Human users (`operator`, `observer`) authenticate through Keycloak Authorization Code + PKCE.
- Pipeline services authenticate through Keycloak Client Credentials (`meridian-pipeline` client).
- API verifies RS256 signatures through Keycloak JWKS and enforces `iss` + `aud` claims.

**API roles**

- `operator` — read + write. Uses `control_plane_writer` DB session.
- `observer` — read-only. Uses `control_plane_reader` DB session.
- `pipeline` — write-only service identity. Uses `ingestion_writer` DB session.

Tokens with zero recognized API roles are rejected. Tokens containing multiple API roles are also rejected.

## Examples

### Get a pipeline token (client credentials)

```bash
TOKEN=$(curl -s -X POST http://localhost:8180/realms/meridian/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=meridian-pipeline" \
  -d "client_secret=pipeline-dev-secret" | jq -r .access_token)
```

### Create a run as pipeline

```bash
curl -s -X POST http://127.0.0.1:8000/runs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_type": "excel_upload", "triggered_by": "airflow_dag"}' | jq
```

### Human user auth in Swagger UI

1. Open `http://127.0.0.1:8000/docs`
2. Click **Authorize**
3. Sign in through Keycloak with `operator` or `observer`
4. Invoke endpoints from Swagger

### Error responses

| Status | Condition |
| --- | --- |
| 401 | No token, expired token, invalid signature, wrong issuer, or wrong audience |
| 403 | Token valid but role insufficient or ambiguous API role mapping |
| 404 | Resource ID not found |
| 422 | Request body validation failure |

## UI Access

| Interface | URL |
| --- | --- |
| Swagger UI | `http://127.0.0.1:8000/docs` |
| ReDoc | `http://127.0.0.1:8000/redoc` |
| Keycloak Admin | `http://localhost:8180` |
| MinIO Console | `http://127.0.0.1:9001` |
