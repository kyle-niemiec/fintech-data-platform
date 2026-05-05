# UI Query API

The UI query API serves UI read models only.

It does not:
- start ingestion runs,
- move payloads,
- write pipeline artifacts,
- orchestrate transformations.

ETL must continue normally if this API is unavailable.

## Base URL

`http://127.0.0.1:8000`

## Authentication

- No human login is required for this demo UI.
- Endpoints are publicly readable in local development.
- Deployments should enforce network-level controls and rate limiting because this API is intentionally anonymous.

## Endpoints (Read-Only)

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/ui/runs` | List runs with pipeline class/name, status, and latest stage |
| `GET` | `/ui/runs/{run_id}` | Get one run summary |
| `GET` | `/ui/runs/{run_id}/artifacts` | List storage artifacts across stages |
| `GET` | `/ui/runs/{run_id}/lineage` | Return transformation chain for the run |
| `GET` | `/ui/runs/{run_id}/events` | Return chronological event timeline |
| `GET` | `/ui/alerts` | List alert feed items for failures/risk events |

## Response Model Principles

- Responses are assembled from event-store read models.
- Event payload data is summarized, not rewritten.
- Every returned entity includes `run_id` + trace identifiers.
- Run records include `pipeline_class`, `pipeline_name`, and `source_system` to keep ingestion and curated domains distinct.
- `pipeline_run` is expected to have at least one event (event-first run contract).
- Artifact trail uses canonical stage metadata (`stage`) plus array-based artifact metadata (`input_uris[]`, `output_uris[]`).
- Artifact trail flattens URI arrays from pipeline events into per-artifact rows with `artifact_role` and `uri`.
- Lineage responses expose canonical URI arrays (`input_uris[]`, `output_uris[]`) for transformation stages.
- Lineage responses expose transformation provenance as `transform_id` and `transform_version` when present.

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
    "message": "File uploaded to landing"
  }
]
```

## Example: Artifact Trail

`GET /ui/runs/{run_id}/artifacts`

```json
[
  {
    "event_id": "ce8c1710-6b7c-46f6-8bc3-d1e0ecf7d951",
    "occurred_at": "2026-04-11T19:25:13Z",
    "stage": "silver",
    "artifact_role": "output",
    "format": "parquet",
    "uri": "s3://lake/silver/domain=payments/year=2026/month=04/day=11/part-0001.parquet",
    "event_type": "pipeline.silver.completed.v1"
  }
]
```

## Example: Lineage

`GET /ui/runs/{run_id}/lineage`

```json
[
  {
    "event_id": "3da4b8de-cd24-4fd4-8792-8b2d12c87dbe",
    "occurred_at": "2026-04-11T19:25:13Z",
    "stage": "silver",
    "input_uris": [
      "s3://lake/bronze/source=cdc/table=transactions/year=2026/month=04/day=11/run_id=..."
    ],
    "output_uris": [
      "s3://lake/silver/domain=payments/year=2026/month=04/day=11/part-0001.parquet",
      "s3://lake/silver/domain=payments/year=2026/month=04/day=11/part-0002.parquet"
    ],
    "transform_id": "normalize_dedupe_mask",
    "transform_version": "v3",
    "event_type": "pipeline.silver.completed.v1"
  }
]
```

## Non-API Actions

UI-triggered demo-data generation is handled by source-adapter services, not this query API:
- Excel demo generator writes to the landing bucket.
- CDC demo generator writes OLTP records that emit Debezium events.
- Salesforce pulls are scheduled internal jobs (no API/UI trigger path).

For Excel demo generation, actor identities are selected from Keycloak `finance` role users by the internal generator service so the API does not hardcode user identities.

## Error Conditions

| Status | Meaning |
| --- | --- |
| `404` | Run or resource not found |
| `429` | Query rate limit exceeded |
| `500` | Read-model/query subsystem failure |
