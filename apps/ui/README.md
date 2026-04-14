# Demo UI

React + TypeScript + Vite + Tailwind SPA for the Meridian Fintech Data Platform.

Served by nginx in the `fintech_ui` container on `http://localhost:3000`.
All data comes from the read-only query API at `http://localhost:8000` (see
[services/ui-api](../../services/ui-api)). The only write action is the demo
upload endpoint (`POST /ui/demo/upload`), which the API performs on MinIO
using the `minio_ingest` principal.

## Pages

| Path | Purpose |
|---|---|
| `/` | List every pipeline run, polled every 5s. Click a row for details. |
| `/runs/:runId` | Events timeline, lineage, and artifacts for one run. |
| `/demo/upload` | Generates a valid `payroll_v1` xlsx and triggers the pipeline as a randomly-selected finance demo user. |

## Layout

```
src/
├── main.tsx, App.tsx, index.css
├── lib/         # apiClient, formatters, queryKeys
├── types/       # API response types (mirrors services/ui-api schemas)
├── hooks/       # useRuns, useRun, useDemoUpload
├── components/
│   ├── layout/      # TopNav, PageContainer
│   ├── common/      # StatusPill, StageBadge, MonoId, ...
│   ├── runs/        # RunsTable, RunSummaryHeader
│   ├── runDetail/   # EventsTimeline, LineageList, ArtifactsTable
│   └── upload/      # UploadCard, GeneratedFilePreview, DemoUserBadge
└── pages/       # RunsPage, RunDetailPage, DemoUploadPage, NotFoundPage
```

## Development

The container uses a multi-stage build (Node → nginx), so source changes
require a rebuild:

```
make infra-ui-up
```

For tighter iteration, run Vite on the host:

```
cd apps/ui
npm install
VITE_API_URL=http://localhost:8000 npm run dev
```

## Configuration

| Var | Default | Purpose |
|---|---|---|
| `VITE_API_URL` (build-time) | `http://localhost:8000` | API origin baked into the bundle. Supplied via the `UI_API_URL` env var in [infra/.env](../../infra/.env). |
| `UI_ORIGIN` (API container) | `http://localhost:3000` | CORS allow-origin the API grants to this SPA. |
