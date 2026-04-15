from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_oltp_db, get_query_db
from app.schemas.ui_query import (
    AlertItem,
    ArtifactTrailItem,
    LineageTrailItem,
    RecentTransactionItem,
    RunDetail,
    RunEventItem,
    RunSummary,
)

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
@router.get("/runs", response_model=list[RunSummary], status_code=status.HTTP_200_OK)
def list_runs(
    db: Session = Depends(get_query_db),
    pipeline_name: list[str] | None = Query(default=None),
):
    params: dict = {}
    filter_sql = ""
    if pipeline_name:
        filter_sql = "WHERE pr.pipeline_name = ANY(:pipeline_names)"
        params["pipeline_names"] = pipeline_name

    rows = db.execute(
        text(
            f"""
            SELECT
                pr.run_id,
                pr.pipeline_class,
                pr.pipeline_name,
                pr.source_system,
                pr.status,
                le.event_type AS latest_stage,
                pr.started_at,
                pr.completed_at
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
            """
        ),
        params,
    ).mappings()

    return [RunSummary(**row) for row in rows]


@router.get(
    "/oltp/transactions/recent",
    response_model=list[RecentTransactionItem],
    status_code=status.HTTP_200_OK,
)
def list_recent_transactions(
    db: Session = Depends(get_oltp_db),
    limit: int = Query(default=25, ge=1, le=100),
):
    rows = db.execute(
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
                rf.fraud_rule_version
            FROM trading.transaction AS t
            LEFT JOIN LATERAL (
                SELECT risk_score, risk_flags, fraud_rule_version
                FROM trading.risk_flag r
                WHERE r.transaction_id = t.transaction_id
                ORDER BY r.flagged_at DESC
                LIMIT 1
            ) AS rf ON true
            ORDER BY t.executed_at DESC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).mappings()
    return [RecentTransactionItem(**row) for row in rows]

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

    # Pass all row fields as parameters to the RunDetail model
    return RunDetail(**row)

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
GET: Return the list of alerts from the event store.
"""
@router.get("/alerts", response_model=list[AlertItem], status_code=status.HTTP_200_OK)
def list_alerts(
    db: Session = Depends(get_query_db),
):
    rows = db.execute(
        text(
            """
            SELECT
                alert_id,
                run_id,
                severity,
                category,
                summary,
                details,
                occurred_at
            FROM event_store.alert_event
            ORDER BY occurred_at DESC
            """
        )
    ).mappings()
    return [AlertItem(**row) for row in rows]
