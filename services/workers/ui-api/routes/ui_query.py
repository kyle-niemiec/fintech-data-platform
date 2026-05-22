from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_oltp_db, get_query_db
from schemas.ui_query import (
    AlertItem,
    ArtifactTrailItem,
    LineageTrailItem,
    Page,
    RecentTransactionItem,
    RunDetail,
    RunEventItem,
    RunSummary,
)


def _page_total(rows: list, count: int) -> int:
    """Read the windowed `total_count` from the first row, falling back to the
    page length when the column is absent (e.g. in unit tests with canned rows).
    """
    if not rows:
        return 0
    return int(rows[0].get("total_count", count))

router = APIRouter(prefix="/ui", tags=["ui"])

"""
A helper function to ensure a run ID exists.
"""
def _assert_run_exists(db: Session, run_id: UUID) -> None:
    exists = db.execute(
        text("SELECT 1 FROM event_store.pipeline_run WHERE run_id = :run_id"),
        {"run_id": run_id},
    ).scalar_one_or_none()

    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

"""
GET: A list of pipeline runs with their latest event status attached.
"""
@router.get("/runs", response_model=Page[RunSummary], status_code=status.HTTP_200_OK)
def list_runs(
    db: Session = Depends(get_query_db),
    pipeline_name: list[str] | None = Query(default=None),
    backfill: bool | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    params: dict = {"limit": limit, "offset": offset}
    conditions: list[str] = []
    if pipeline_name:
        conditions.append("pr.pipeline_name = ANY(:pipeline_names)")
        params["pipeline_names"] = pipeline_name
    if backfill is not None:
        # Mirror the Python `is_backfill` derivation in SQL so the filter and the
        # row flag below always agree.
        backfill_expr = (
            "(strpos(coalesce(pr.trigger_event_ref, ''), 'backfill_') > 0"
            " OR pr.trigger_type = 'backfill')"
        )
        conditions.append(backfill_expr if backfill else f"NOT {backfill_expr}")
    filter_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = list(
        db.execute(
            text(
                f"""
                SELECT
                    pr.run_id,
                    pr.pipeline_class,
                    pr.pipeline_name,
                    pr.source_system,
                    pr.status,
                    pr.trigger_event_ref,
                    pr.trigger_type,
                    le.event_type AS latest_stage,
                    pr.started_at,
                    pr.completed_at,
                    count(*) OVER() AS total_count
                FROM event_store.pipeline_run AS pr
                    JOIN LATERAL (
                        SELECT event_type
                        FROM event_store.event_log el
                        WHERE el.run_id = pr.run_id
                        ORDER BY el.occurred_at DESC
                        LIMIT 1
                    ) AS le ON true
                {filter_sql}
                ORDER BY pr.started_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings()
    )

    items = [
        RunSummary(
            run_id=row["run_id"],
            pipeline_class=row["pipeline_class"],
            pipeline_name=row["pipeline_name"],
            source_system=row["source_system"],
            status=row["status"],
            latest_stage=row["latest_stage"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            is_backfill=(
                "backfill_" in (row.get("trigger_event_ref") or "")
                or row.get("trigger_type") == "backfill"
            ),
        )
        for row in rows
    ]
    return Page(items=items, total=_page_total(rows, len(items)), limit=limit, offset=offset)


@router.get(
    "/oltp/transactions/recent",
    response_model=Page[RecentTransactionItem],
    status_code=status.HTTP_200_OK,
)
def list_recent_transactions(
    db: Session = Depends(get_oltp_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    rows = list(
        db.execute(
            text(
                """
                SELECT
                    t.transaction_id,
                    t.account_id,
                    t.instrument,
                    t.amount,
                    t.executed_at,
                    rf.risk_score,
                    rf.risk_flags,
                    count(*) OVER() AS total_count
                FROM trading.transaction AS t
                LEFT JOIN LATERAL (
                    SELECT risk_score, risk_flags
                    FROM trading.risk_flag r
                    WHERE r.transaction_id = t.transaction_id
                    ORDER BY r.flagged_at DESC
                    LIMIT 1
                ) AS rf ON true
                ORDER BY t.executed_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).mappings()
    )
    items = [
        RecentTransactionItem(**{k: v for k, v in row.items() if k != "total_count"})
        for row in rows
    ]
    return Page(items=items, total=_page_total(rows, len(items)), limit=limit, offset=offset)

"""
GET: A single pipeline run by ID along with the latest event status.
"""
@router.get("/runs/{run_id}", response_model=RunDetail, status_code=status.HTTP_200_OK)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_query_db),
):
    _assert_run_exists(db, run_id)

    row = db.execute(
        text(
            """
            SELECT
                pr.run_id,
                pr.pipeline_class,
                pr.pipeline_name,
                pr.source_system,
                pr.trigger_type,
                pr.trigger_event_ref,
                pr.status,
                pr.initiator,
                pr.parent_run_id,
                pr.started_at,
                pr.completed_at,
                le.event_type AS latest_stage
            FROM event_store.pipeline_run pr
                JOIN LATERAL (
                    SELECT event_type
                    FROM event_store.event_log el
                    WHERE el.run_id = pr.run_id
                    ORDER BY el.occurred_at DESC
                    LIMIT 1
                ) AS le ON true
            WHERE pr.run_id = :run_id
            """
        ),
        {"run_id": run_id},
    ).mappings().one_or_none()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run exists without events; event-first invariant violated",
        )

    return RunDetail(
        **row,
        is_backfill=(
            "backfill_" in (row["trigger_event_ref"] or "")
            or row.get("trigger_type") == "backfill"
        ),
    )

"""
GET: Retrieve all artifacts for a given run ID.
"""
@router.get(
    "/runs/{run_id}/artifacts",
    response_model=list[ArtifactTrailItem],
    status_code=status.HTTP_200_OK,
)
def list_artifacts(
    run_id: UUID,
    db: Session = Depends(get_query_db),
):
    _assert_run_exists(db, run_id)

    rows = db.execute(
        text(
            """
            SELECT
                el.event_id,
                el.occurred_at,

                COALESCE(
                    el.payload->>'stage',
                    CASE
                        WHEN el.event_type LIKE '%.raw.ready.%' THEN 'raw'
                        WHEN el.event_type LIKE '%.quarantined.%' THEN 'quarantine'
                        WHEN el.event_type LIKE '%.bronze.ready.%' THEN 'bronze'
                        WHEN el.event_type LIKE 'pipeline.silver.%' THEN 'silver'
                        WHEN el.event_type LIKE 'pipeline.gold.%' THEN 'gold'
                        ELSE NULL
                    END
                ) AS stage,

                artifact_item.artifact_role,
                el.payload->>'format' AS format,
                artifact_item.uri,
                el.event_type
            FROM event_store.event_log AS el
                JOIN LATERAL (
                    /*
                     * Retrieve `input_uris[]`/`output_uris[]` fields for pipeline artifacts,
                     * then return the combined list.
                     */

                    SELECT 'input'::text AS artifact_role, input_uri.uri
                    FROM jsonb_array_elements_text(
                        CASE
                            WHEN jsonb_typeof(el.payload->'input_uris') = 'array' THEN el.payload->'input_uris'
                            ELSE '[]'::jsonb
                        END
                    ) AS input_uri(uri)
                    WHERE nullif(trim(input_uri.uri), '') IS NOT NULL

                    UNION ALL

                    SELECT 'output'::text AS artifact_role, output_uri.uri
                    FROM jsonb_array_elements_text(
                        CASE
                            WHEN jsonb_typeof(el.payload->'output_uris') = 'array' THEN el.payload->'output_uris'
                            ELSE '[]'::jsonb
                        END
                    ) AS output_uri(uri)
                    WHERE nullif(trim(output_uri.uri), '') IS NOT NULL

                ) AS artifact_item ON true
            WHERE el.run_id = :run_id
            ORDER BY el.occurred_at ASC, el.event_id ASC, artifact_item.artifact_role ASC, artifact_item.uri ASC
            """
        ),
        {"run_id": run_id},
    ).mappings()
    return [ArtifactTrailItem(**row) for row in rows]

"""
GET: Retrieve lineage references for a given run ID.
"""
@router.get(
    "/runs/{run_id}/lineage",
    response_model=list[LineageTrailItem],
    status_code=status.HTTP_200_OK,
)
def list_lineage(
    run_id: UUID,
    db: Session = Depends(get_query_db),
):
    _assert_run_exists(db, run_id)
    rows = db.execute(
        text(
            """
            SELECT
                el.event_id,
                el.occurred_at,

                COALESCE(
                    el.payload->>'stage',
                    CASE
                        WHEN el.event_type LIKE '%.raw.ready.%' THEN 'raw'
                        WHEN el.event_type LIKE '%.quarantined.%' THEN 'quarantine'
                        WHEN el.event_type LIKE '%.bronze.ready.%' THEN 'bronze'
                        WHEN el.event_type LIKE 'pipeline.silver.%' THEN 'silver'
                        WHEN el.event_type LIKE 'pipeline.gold.%' THEN 'gold'
                        ELSE NULL
                    END
                ) AS stage,

                CASE
                    WHEN jsonb_typeof(el.payload->'input_uris') = 'array'
                        THEN ARRAY(SELECT jsonb_array_elements_text(el.payload->'input_uris'))
                    ELSE ARRAY[]::text[]
                END AS input_uris,

                CASE
                    WHEN jsonb_typeof(el.payload->'output_uris') = 'array'
                        THEN ARRAY(SELECT jsonb_array_elements_text(el.payload->'output_uris'))
                    ELSE ARRAY[]::text[]
                END AS output_uris,

                el.payload->>'transform_id' AS transform_id,
                el.payload->>'transform_version' AS transform_version,
                el.event_type
            FROM event_store.event_log el
            WHERE el.run_id = :run_id
              AND (
                    el.payload ? 'input_uris'
                 OR el.payload ? 'output_uris'
                 OR el.payload ? 'transform_id'
                 OR el.payload ? 'transform_version'
              )
            ORDER BY el.occurred_at ASC
            """
        ),
        {"run_id": run_id},
    ).mappings()
    return [LineageTrailItem(**row) for row in rows]

"""
GET: A list of events associated with a run ID.
"""
@router.get(
    "/runs/{run_id}/events",
    response_model=list[RunEventItem],
    status_code=status.HTTP_200_OK,
)
def list_events(
    run_id: UUID,
    db: Session = Depends(get_query_db),
):
    _assert_run_exists(db, run_id)
    rows = db.execute(
        text(
            """
            SELECT
                el.occurred_at,
                el.event_type,
                split_part(el.event_type, '.', 1) AS source,
                el.run_id,
                el.trace_id,
                el.payload->>'message' AS message
            FROM event_store.event_log AS el
            WHERE el.run_id = :run_id
            ORDER BY el.occurred_at ASC
            """
        ),
        {"run_id": run_id},
    ).mappings()
    return [RunEventItem(**row) for row in rows]

"""
GET: Return the alert feed from the event store, newest first.

Optionally scoped to a single run via `run_id` and bounded by `limit` so the
read-only feed cannot return an unbounded result set.
"""
@router.get("/alerts", response_model=Page[AlertItem], status_code=status.HTTP_200_OK)
def list_alerts(
    db: Session = Depends(get_query_db),
    run_id: UUID | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    params: dict = {"limit": limit, "offset": offset}
    filter_sql = ""
    if run_id is not None:
        filter_sql = "WHERE run_id = :run_id"
        params["run_id"] = run_id

    rows = list(
        db.execute(
            text(
                f"""
                SELECT
                    alert_id,
                    run_id,
                    severity,
                    category,
                    summary,
                    details,
                    occurred_at,
                    count(*) OVER() AS total_count
                FROM event_store.alert_event
                {filter_sql}
                ORDER BY occurred_at DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            params,
        ).mappings()
    )
    items = [
        AlertItem(**{k: v for k, v in row.items() if k != "total_count"}) for row in rows
    ]
    return Page(items=items, total=_page_total(rows, len(items)), limit=limit, offset=offset)
