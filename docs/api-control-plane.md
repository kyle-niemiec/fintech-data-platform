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

Lineage records are intentionally only listable by `run_id` — there is no `GET /lineage/{lineage_id}` endpoint, because individual lineage rows are only meaningful in the context of the run that produced them.

## Authentication

Authentication is delegated to Keycloak — see [security-access.md](security-access.md#api-authentication) for the full description of the realm, clients, JWT validation, and role mapping. The short version:

- Human users sign in via the `meridian-api` public client (Authorization Code + PKCE).
- Pipeline services obtain tokens via the `meridian-pipeline` confidential client (Client Credentials).
- The API validates RS256 signatures, `iss`, `aud` (`meridian-api`), and expiry.
- The API role (`operator`, `observer`, or `pipeline`) is read from `resource_access.meridian-api.roles`. Tokens with zero or multiple recognized API roles are rejected.
- Write operations persist actor attribution (`actor_sub`, `actor_role`) from the validated token onto every row they create.

## Examples

### Get a pipeline token (client credentials)

```bash
TOKEN=$(curl -s -X POST http://localhost:8180/realms/meridian/protocol/openid-connect/token \
  -d "grant_type=client_credentials" \
  -d "client_id=meridian-pipeline" \
  -d "client_secret=$KC_PIPELINE_CLIENT_SECRET" | jq -r .access_token)
```

### Create a run as pipeline

```bash
curl -s -X POST http://127.0.0.1:8000/runs/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_type": "excel_upload"}' | jq
```

Expected response fields include:
- `actor_sub` (token `sub`)
- `actor_role` (`operator` or `pipeline` for writes)

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
