from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from db import get_oltp_db, get_query_db
from schemas.ui_query import (
    AlertItem,
    ArtifactTrailItem,
    ExcelPreview,
    LineageTrailItem,
    Page,
    RecentTransactionItem,
    RunDetail,
    RunEventItem,
    RunPreviewResponse,
    RunSummary,
)
from services.minio_upload import MinioUploadError, read_object, split_s3_uri
from services.run_preview import PREVIEW_ROW_LIMIT, parse_xlsx_preview


def _page_total(rows: list, count: int) -> int:
    """Read the windowed `total_count` from the first row, falling back to the
    page length when the column is absent (e.g. in unit tests with canned rows).
    """
    if not rows:
        return 0
    return int(rows[0].get("total_count", count))


# Server-side sort: each entry maps a client sort key to a fixed primary SQL
# expression. ORDER BY is built only from these constants (never raw input), so
# `sort`/`dir` cannot inject SQL; an unknown key falls back to `default_key`.
RUNS_SORT = {
    "run_id": "pr.run_id::text",
    "pipeline": "pr.pipeline_name",
    "status": "pr.status",
    "started": "pr.started_at",
    "duration": "(coalesce(pr.completed_at, now()) - pr.started_at)",
}
RECENT_TX_SORT = {
    "executed": "t.executed_at",
    "transaction": "t.transaction_id::text",
    "account": "t.account_id::text",
    "instrument": "t.instrument",
    "risk_score": "rf.risk_score",
}
ALERTS_SORT = {
    "occurred": "occurred_at",
    "severity": "CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 WHEN 'low' THEN 2 ELSE 3 END",
    "category": "category",
    "run": "run_id::text",
}


def _order_by(
    sort: str | None,
    direction: str | None,
    *,
    spec: dict[str, str],
    default_key: str,
    default_dir: str,
    recency_sql: str,
    unique_sql: str,
    nulls_last: tuple[str, ...] = (),
) -> str:
    """Build a safe ORDER BY clause from a whitelist `spec`.

    The chosen column sorts in `direction` (validated to ASC/DESC); a fixed
    recency tiebreaker is appended for non-default columns, and `unique_sql`
    always ends the clause so pagination stays deterministic.
    """
    key = sort if isinstance(sort, str) and sort in spec else default_key
    d = direction.lower() if isinstance(direction, str) else ""
    if d not in ("asc", "desc"):
        d = default_dir
    primary = f"{spec[key]} {d.upper()}"
    if key in nulls_last:
        primary += " NULLS LAST"
    parts = [primary]
    if key != default_key:
        parts.append(recency_sql)
    parts.append(unique_sql)
    return "ORDER BY " + ", ".join(parts)

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
    sort: str | None = Query(default=None),
    direction: str | None = Query(default=None, alias="dir"),
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
    order_sql = _order_by(
        sort,
        direction,
        spec=RUNS_SORT,
        default_key="started",
        default_dir="desc",
        recency_sql="pr.started_at DESC",
        unique_sql="pr.run_id",
    )

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
                {order_sql}
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
    query_db: Session = Depends(get_query_db),
    sort: str | None = Query(default=None),
    direction: str | None = Query(default=None, alias="dir"),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    order_sql = _order_by(
        sort,
        direction,
        spec=RECENT_TX_SORT,
        default_key="executed",
        default_dir="desc",
        recency_sql="t.executed_at DESC",
        unique_sql="t.transaction_id",
        nulls_last=("risk_score",),
    )
    rows = list(
        db.execute(
            text(
                f"""
                SELECT
                    t.transaction_id,
                    t.account_id,
                    t.instrument,
                    t.amount,
                    t.executed_at,
                    t.origin,
                    rf.risk_score,
                    rf.risk_flags,
                    rf.event_id,
                    count(*) OVER() AS total_count
                FROM trading.transaction AS t
                LEFT JOIN LATERAL (
                    SELECT risk_score, risk_flags, event_id
                    FROM trading.risk_flag r
                    WHERE r.transaction_id = t.transaction_id
                    ORDER BY r.flagged_at DESC
                    LIMIT 1
                ) AS rf ON true
                {order_sql}
                LIMIT :limit OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        ).mappings()
    )

    # Resolve each scored transaction's CDC run. rf.event_id is the assessed
    # event's id (fraud_worker writes it to both risk_flag and event_log), so
    # this is an exact PK lookup against the (separate) event-store database.
    run_by_event = _runs_for_event_ids(
        query_db, [row["event_id"] for row in rows if row.get("event_id")]
    )

    items = [
        RecentTransactionItem(
            **{k: v for k, v in row.items() if k not in ("total_count", "event_id")},
            run_id=run_by_event.get(row.get("event_id")),
        )
        for row in rows
    ]
    return Page(items=items, total=_page_total(rows, len(items)), limit=limit, offset=offset)


def _runs_for_event_ids(query_db: Session, event_ids: list) -> dict:
    """Map assessed event_ids to their run_id via the event-store PK. Returns an
    empty map (and issues no query) when there are no scored transactions."""
    if not event_ids:
        return {}
    link_rows = query_db.execute(
        text(
            "SELECT event_id, run_id FROM event_store.event_log "
            "WHERE event_id = ANY(:event_ids)"
        ),
        {"event_ids": event_ids},
    ).mappings()
    return {row["event_id"]: row["run_id"] for row in link_rows}

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
        preview_kind=_derive_preview_kind(
            db, run_id, row["pipeline_name"], row["status"]
        ),
    )


# Excel runs in these terminal states never expose a preview (the workbook was
# rejected before/at scan, so its rows must not be served).
_EXCEL_NO_PREVIEW_STATUSES = ("quarantined", "scan_failed")


def _derive_preview_kind(
    db: Session, run_id: UUID, pipeline_name: str, run_status: str
) -> str | None:
    """Classify a run for the Preview tab without shipping any preview data.

    'cdc_transaction' for CDC runs that scored a trading.transaction row,
    'excel' for non-quarantined Excel ingestion runs, else None.
    """
    if pipeline_name == "cdc_ingestion":
        is_transaction = db.execute(
            text(
                """
                SELECT 1
                FROM event_store.event_log
                WHERE run_id = :run_id
                  AND payload->>'source_table' = 'trading.transaction'
                LIMIT 1
                """
            ),
            {"run_id": run_id},
        ).scalar_one_or_none()
        return "cdc_transaction" if is_transaction is not None else None
    if pipeline_name == "excel_ingestion" and run_status not in _EXCEL_NO_PREVIEW_STATUSES:
        return "excel"
    return None


"""
GET: Read-only preview for a run. Returns the scored transaction's details for a
CDC-transaction run, or the first rows of the uploaded sheet for an Excel run.
Re-derives the same gate as `preview_kind` and returns 404 for any other run
(loan/payment CDC, quarantined Excel, Salesforce, curated), so preview data is
never served for ineligible runs.
"""
@router.get(
    "/runs/{run_id}/preview",
    response_model=RunPreviewResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_preview(
    run_id: UUID,
    db: Session = Depends(get_query_db),
    oltp_db: Session = Depends(get_oltp_db),
):
    _assert_run_exists(db, run_id)
    meta = db.execute(
        text(
            "SELECT pipeline_name, status FROM event_store.pipeline_run "
            "WHERE run_id = :run_id"
        ),
        {"run_id": run_id},
    ).mappings().one_or_none()
    if meta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    kind = _derive_preview_kind(db, run_id, meta["pipeline_name"], meta["status"])
    if kind == "cdc_transaction":
        transaction = _cdc_transaction_preview(db, oltp_db, run_id)
        if transaction is not None:
            return RunPreviewResponse(kind=kind, transaction=transaction)
    elif kind == "excel":
        excel = _excel_preview(db, run_id)
        if excel is not None:
            return RunPreviewResponse(kind=kind, excel=excel)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No preview available for this run",
    )


def _cdc_transaction_preview(
    db: Session, oltp_db: Session, run_id: UUID
) -> RecentTransactionItem | None:
    """Resolve the run's transaction_id from its assessed event, then read the
    transaction's details from OLTP (same fields as the transactions page)."""
    transaction_id = db.execute(
        text(
            """
            SELECT payload->>'transaction_id' AS transaction_id
            FROM event_store.event_log
            WHERE run_id = :run_id
              AND payload->>'source_table' = 'trading.transaction'
              AND payload ? 'transaction_id'
            ORDER BY occurred_at DESC
            LIMIT 1
            """
        ),
        {"run_id": run_id},
    ).scalar_one_or_none()
    if not transaction_id:
        return None

    row = oltp_db.execute(
        text(
            """
            SELECT
                t.transaction_id,
                t.account_id,
                t.instrument,
                t.amount,
                t.executed_at,
                t.origin,
                rf.risk_score,
                rf.risk_flags
            FROM trading.transaction AS t
            LEFT JOIN LATERAL (
                SELECT risk_score, risk_flags
                FROM trading.risk_flag r
                WHERE r.transaction_id = t.transaction_id
                ORDER BY r.flagged_at DESC
                LIMIT 1
            ) AS rf ON true
            WHERE t.transaction_id = CAST(:transaction_id AS uuid)
            """
        ),
        {"transaction_id": transaction_id},
    ).mappings().one_or_none()
    if row is None:
        return None
    return RecentTransactionItem(**row, run_id=run_id)


def _excel_preview(db: Session, run_id: UUID) -> ExcelPreview | None:
    """Resolve the run's raw .xlsx URI from its events, read it from MinIO, and
    return the first rows of the first sheet."""
    uri = db.execute(
        text(
            """
            SELECT uris.uri
            FROM event_store.event_log AS el
                JOIN LATERAL (
                    SELECT u.uri
                    FROM jsonb_array_elements_text(
                        CASE
                            WHEN jsonb_typeof(el.payload->'input_uris') = 'array' THEN el.payload->'input_uris'
                            ELSE '[]'::jsonb
                        END
                        ||
                        CASE
                            WHEN jsonb_typeof(el.payload->'output_uris') = 'array' THEN el.payload->'output_uris'
                            ELSE '[]'::jsonb
                        END
                    ) AS u(uri)
                ) AS uris ON true
            WHERE el.run_id = :run_id
              AND lower(uris.uri) LIKE '%.xlsx'
            ORDER BY el.occurred_at ASC
            LIMIT 1
            """
        ),
        {"run_id": run_id},
    ).scalar_one_or_none()
    if not uri:
        return None

    try:
        bucket, key = split_s3_uri(uri)
        data = read_object(bucket=bucket, key=key)
    except MinioUploadError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Could not read preview object: {exc}",
        ) from exc

    sheet_name, columns, rows = parse_xlsx_preview(data, max_rows=PREVIEW_ROW_LIMIT)
    return ExcelPreview(sheet_name=sheet_name, columns=columns, rows=rows)

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
    sort: str | None = Query(default=None),
    direction: str | None = Query(default=None, alias="dir"),
    limit: int = Query(default=25, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    params: dict = {"limit": limit, "offset": offset}
    filter_sql = ""
    if run_id is not None:
        filter_sql = "WHERE run_id = :run_id"
        params["run_id"] = run_id
    order_sql = _order_by(
        sort,
        direction,
        spec=ALERTS_SORT,
        default_key="occurred",
        default_dir="desc",
        recency_sql="occurred_at DESC",
        unique_sql="alert_id",
    )

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
                {order_sql}
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
