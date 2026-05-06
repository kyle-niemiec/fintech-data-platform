from __future__ import annotations

import logging
from typing import Any

from curated_sql_helpers import sql_bool_literal, sql_string_literal
from silver_curated.common import _trino_cursor

logger = logging.getLogger(__name__)

MERGE_SQL = """
MERGE INTO lakehouse.silver.dim_opportunity AS tgt
USING (
    WITH staged_input (
        opportunity_id,
        account_id_token,
        name,
        stage_name,
        amount,
        close_date,
        is_won,
        is_closed,
        source_system_mod
    ) AS (
        VALUES
        {source_rows_values}
    )

    SELECT
        opportunity_id,
        account_id_token,
        name,
        stage_name,
        CAST(amount AS DECIMAL(18, 2)) AS amount,
        CAST(close_date AS DATE) AS close_date,
        is_won,
        is_closed,
        COALESCE(
            TRY(CAST(source_system_mod AS TIMESTAMP(6) WITH TIME ZONE)),
            CAST(from_iso8601_timestamp(source_system_mod) AS TIMESTAMP(6) WITH TIME ZONE)
        ) AS source_system_mod,
        CAST({parent_run_id} AS VARCHAR) AS source_run_id,
        CAST({curated_run_id} AS VARCHAR) AS curated_run_id
    FROM staged_input
) AS src
ON  tgt.opportunity_id = src.opportunity_id
AND tgt.is_current = true
WHEN MATCHED AND (
        tgt.stage_name IS DISTINCT FROM src.stage_name
     OR tgt.amount     IS DISTINCT FROM src.amount
     OR tgt.close_date IS DISTINCT FROM src.close_date
     OR tgt.is_won     IS DISTINCT FROM src.is_won
     OR tgt.is_closed  IS DISTINCT FROM src.is_closed
    )
    THEN UPDATE SET
        valid_to   = src.source_system_mod,
        is_current = false
WHEN NOT MATCHED
    THEN INSERT (
        opportunity_id, account_id_token, name, stage_name, amount, close_date,
        is_won, is_closed, valid_from, valid_to, is_current,
        source_run_id, curated_run_id, source_system_mod,
        year, month, day
    )
    VALUES (
        src.opportunity_id, src.account_id_token, src.name, src.stage_name,
        src.amount, src.close_date, src.is_won, src.is_closed,
        src.source_system_mod, NULL, true,
        src.source_run_id, src.curated_run_id, src.source_system_mod,
        year(src.source_system_mod), month(src.source_system_mod), day(src.source_system_mod)
    )
"""


def _build_merge_sql(
    *,
    source_rows_values: str,
    parent_run_id: str,
    curated_run_id: str,
) -> str:
    return MERGE_SQL.format(
        source_rows_values=source_rows_values,
        parent_run_id=sql_string_literal(parent_run_id),
        curated_run_id=sql_string_literal(curated_run_id),
    ).strip()


def merge_into_silver(state: dict[str, Any]) -> dict[str, Any]:
    masked_rows = list(state.get("masked_rows") or [])

    row_values_sql = []
    for row in masked_rows:
        row_values_sql.append(
            "("
            f"{sql_string_literal(row.get('opportunity_id'))}, "
            f"{sql_string_literal(row.get('account_id_token'))}, "
            f"{sql_string_literal(row.get('name'))}, "
            f"{sql_string_literal(row.get('stage_name'))}, "
            f"{sql_string_literal(row.get('amount'))}, "
            f"{sql_string_literal(row.get('close_date'))}, "
            f"{sql_bool_literal(row.get('is_won'))}, "
            f"{sql_bool_literal(row.get('is_closed'))}, "
            f"{sql_string_literal(row.get('source_system_mod'))}"
            ")"
        )

    merge_sql = _build_merge_sql(
        source_rows_values=",\n        ".join(row_values_sql),
        parent_run_id=state["parent_run_id"],
        curated_run_id=state["curated_run_id"],
    )

    conn, cur = _trino_cursor()

    try:
        merge_stats: dict[str, int] = {"inserted": 0, "updated": 0, "closed": 0}

        if not row_values_sql:
            logger.info("no masked rows available for merge; skipping MERGE statement")
            return {**state, "merge_stats": merge_stats}

        cur.execute(merge_sql.strip().rstrip(";"))
        cur.fetchall()
    finally:
        cur.close()
        conn.close()

    return {
        **state,
        "merge_stats": merge_stats,
    }
