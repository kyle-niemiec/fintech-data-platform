# UI Query API

The backend API serves UI read models only.

It does not:
- start ingestion runs,
- move payloads,
- write pipeline artifacts,
- orchestrate transformations.

ETL must continue normally if this API is unavailable.

## Base URL

`http://127.0.0.1:8000`

## Authentication

- OIDC via Keycloak for UI users.
- API validates issuer, audience, signature, and expiry.
- Read-only roles can query run state, lineage traces, and alerts.

## Endpoints (Read-Only)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/ui/runs` | List runs with source, status, and latest stage |
| `GET` | `/ui/runs/{run_id}` | Get one run summary |
| `GET` | `/ui/runs/{run_id}/artifacts` | List storage artifacts across stages |
| `GET` | `/ui/runs/{run_id}/lineage` | Return transformation chain for the run |
| `GET` | `/ui/runs/{run_id}/events` | Return chronological event timeline |
| `GET` | `/ui/alerts` | List alert feed items for failures/risk events |
| `GET` | `/ui/health/pipelines` | Read-only aggregate health of pipeline subsystems |

## Response Model Principles

- Responses are assembled from event-store read models.
- Event payload data is summarized, not rewritten.
- Every returned entity includes `run_id` + trace identifiers.

## Example: Run Timeline

`GET /ui/runs/{run_id}/events`

```json
[
  {
    "occurred_at": "2026-04-11T19:21:00Z",
    "event_type": "ingest.excel.uploaded.v1",
    "source": "excel",
    "run_id": "5c55f9db-3be7-4e9c-a2c9-a458bb2f0e8f",
    "trace_id": "f3a17eef-d0fc-4e31-8f8c-c312f3bd72e0",
    "summary": "File uploaded to landing"
  }
]
```

## Non-API Actions

UI-triggered demo-data generation is handled by source-adapter services, not this query API:
- Excel demo generator writes to the landing bucket.
- CDC demo generator writes OLTP records that emit Debezium events.
- Salesforce demo generator triggers pull jobs through extractor controls.

## Error Conditions

| Status | Meaning |
| --- | --- |
| `401` | Token missing/invalid/expired |
| `403` | Role lacks read access |
| `404` | Run or resource not found |
| `429` | Query rate limit exceeded |
| `500` | Read-model/query subsystem failure |
