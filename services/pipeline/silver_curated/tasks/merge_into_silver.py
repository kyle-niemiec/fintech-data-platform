from __future__ import annotations

import logging
from typing import Any

from curated_sql_helpers import sql_bool_literal, sql_string_literal
from silver_curated.common import _trino_cursor

logger = logging.getLogger(__name__)


def _ts_expr(value_col: str) -> str:
    """
    Return a SQL expression that attempts to parse the given value column as a timestamp with timezone.
    """
    return (
        "COALESCE("
        f"TRY(CAST({value_col} AS TIMESTAMP(6) WITH TIME ZONE)), "
        f"TRY(CAST(from_iso8601_timestamp({value_col}) AS TIMESTAMP(6) WITH TIME ZONE)), "
        "current_timestamp"
        ")"
    )


def _run_sql(sql: str) -> None:
    """
    Run the given SQL statement using a Trino cursor.
    """
    conn, cur = _trino_cursor()

    try:
        cur.execute(sql.strip().rstrip(";"))
        cur.fetchall()
    finally:
        cur.close()
        conn.close()


def _build_values(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> str:
    """
    Build a SQL VALUES clause from the given rows and columns. The columns parameter
    is a list of tuples where each tuple contains the column name and its data type.
    """
    values_sql: list[str] = []

    # Iterate over the rows and construct a SQL literal for each column based on its data type.
    for row in rows:
        row_values: list[str] = []

        # Iterate over the columns and construct a SQL literal for each column based on its data type.
        for key, kind in columns:
            value = row.get(key)

            if kind == "bool":
                row_values.append(sql_bool_literal(value))
            else:
                row_values.append(sql_string_literal(value))

        # Join the row values into a single SQL literal with enclosing parentheses and append it to the list of values.
        values_sql.append("(" + ", ".join(row_values) + ")")

    # Return the constructed VALUES clause with indentation.
    return ",\n        ".join(values_sql)


def _merge_opportunity(*, rows_sql: str, parent_run_id: str, curated_run_id: str) -> str:
    """
    Return the SQL statement responsible for merging Salesforce opportunities
    into the `dim_opportunity` silver table. 
    """
    return f"""
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
        {rows_sql}
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
        {_ts_expr('source_system_mod')} AS source_system_mod,
        CAST({sql_string_literal(parent_run_id)} AS VARCHAR) AS source_run_id,
        CAST({sql_string_literal(curated_run_id)} AS VARCHAR) AS curated_run_id
    FROM staged_input
) AS src
ON tgt.opportunity_id = src.opportunity_id
AND tgt.is_current = true
WHEN MATCHED AND (
       tgt.stage_name IS DISTINCT FROM src.stage_name
    OR tgt.amount IS DISTINCT FROM src.amount
    OR tgt.close_date IS DISTINCT FROM src.close_date
    OR tgt.is_won IS DISTINCT FROM src.is_won
    OR tgt.is_closed IS DISTINCT FROM src.is_closed
)
THEN UPDATE SET
    valid_to = src.source_system_mod,
    is_current = false
WHEN NOT MATCHED
THEN INSERT (
    opportunity_id, account_id_token, name, stage_name, amount, close_date,
    is_won, is_closed, valid_from, valid_to, is_current,
    source_run_id, curated_run_id, source_system_mod, year, month, day
)
VALUES (
    src.opportunity_id, src.account_id_token, src.name, src.stage_name,
    src.amount, src.close_date, src.is_won, src.is_closed,
    src.source_system_mod, NULL, true,
    src.source_run_id, src.curated_run_id, src.source_system_mod,
    year(src.source_system_mod), month(src.source_system_mod), day(src.source_system_mod)
)
"""


def _merge_account(*, rows_sql: str, parent_run_id: str, curated_run_id: str) -> str:
    """
    Return the SQL statement responsible for merging Salesforce accounts into
    the `dim_account` silver table.
    """
    return f"""
MERGE INTO lakehouse.silver.dim_account AS tgt
USING (
    WITH staged_input (
        account_id_token,
        name,
        industry,
        annual_revenue,
        number_of_employees,
        source_system_mod
    ) AS (
        VALUES
        {rows_sql}
    )
    SELECT
        account_id_token,
        name,
        industry,
        CAST(annual_revenue AS DECIMAL(18, 2)) AS annual_revenue,
        CAST(number_of_employees AS INTEGER) AS number_of_employees,
        {_ts_expr('source_system_mod')} AS source_system_mod,
        CAST({sql_string_literal(parent_run_id)} AS VARCHAR) AS source_run_id,
        CAST({sql_string_literal(curated_run_id)} AS VARCHAR) AS curated_run_id
    FROM staged_input
) AS src
ON tgt.account_id_token = src.account_id_token
AND tgt.is_current = true
WHEN MATCHED AND (
       tgt.name IS DISTINCT FROM src.name
    OR tgt.industry IS DISTINCT FROM src.industry
    OR tgt.annual_revenue IS DISTINCT FROM src.annual_revenue
    OR tgt.number_of_employees IS DISTINCT FROM src.number_of_employees
)
THEN UPDATE SET
    valid_to = src.source_system_mod,
    is_current = false
WHEN NOT MATCHED
THEN INSERT (
    account_id_token, name, industry, annual_revenue, number_of_employees,
    valid_from, valid_to, is_current, source_run_id, curated_run_id,
    source_system_mod, year, month, day
)
VALUES (
    src.account_id_token, src.name, src.industry, src.annual_revenue, src.number_of_employees,
    src.source_system_mod, NULL, true, src.source_run_id, src.curated_run_id,
    src.source_system_mod, year(src.source_system_mod), month(src.source_system_mod), day(src.source_system_mod)
)
"""


def _merge_dim_loan(*, rows_sql: str, parent_run_id: str, curated_run_id: str) -> str:
    """
    Return the SQL statement responsible for merging loan records into the `dim_loan`
    silver table.
    """
    return f"""
MERGE INTO lakehouse.silver.dim_loan AS tgt
USING (
    WITH staged_input (
        loan_id, account_id, status_code, principal_balance, days_past_due, source_system_mod
    ) AS (
        VALUES
        {rows_sql}
    )
    SELECT
        CAST(loan_id AS VARCHAR) AS loan_id,
        CAST(account_id AS VARCHAR) AS account_id,
        CAST(status_code AS VARCHAR) AS status_code,
        CAST(principal_balance AS DECIMAL(18, 2)) AS principal_balance,
        CAST(days_past_due AS INTEGER) AS days_past_due,
        {_ts_expr('source_system_mod')} AS source_system_mod,
        CAST({sql_string_literal(parent_run_id)} AS VARCHAR) AS source_run_id,
        CAST({sql_string_literal(curated_run_id)} AS VARCHAR) AS curated_run_id
    FROM staged_input
) AS src
ON tgt.loan_id = src.loan_id
AND tgt.is_current = true
WHEN MATCHED AND (
       tgt.status_code IS DISTINCT FROM src.status_code
    OR tgt.principal_balance IS DISTINCT FROM src.principal_balance
    OR tgt.days_past_due IS DISTINCT FROM src.days_past_due
)
THEN UPDATE SET
    valid_to = src.source_system_mod,
    is_current = false
WHEN NOT MATCHED
THEN INSERT (
    loan_id, account_id, status_code, principal_balance, days_past_due,
    valid_from, valid_to, is_current, source_run_id, curated_run_id,
    source_system_mod, year, month, day
)
VALUES (
    src.loan_id, src.account_id, src.status_code, src.principal_balance, src.days_past_due,
    src.source_system_mod, NULL, true, src.source_run_id, src.curated_run_id,
    src.source_system_mod, year(src.source_system_mod), month(src.source_system_mod), day(src.source_system_mod)
)
"""


def _insert_fact_loan_payment(*, rows_sql: str, parent_run_id: str, curated_run_id: str) -> str:
    """
    Return the SQL statement responsible for inserting loan payment records into
    the `fact_loan_payment` silver table.
    """
    return f"""
INSERT INTO lakehouse.silver.fact_loan_payment
SELECT
    CAST(loan_id AS VARCHAR) AS loan_id,
    CAST(payment_amount AS DECIMAL(18, 2)) AS payment_amount,
    CAST(payment_due_date AS DATE) AS payment_due_date,
    CAST(payment_posted_at AS DATE) AS payment_posted_at,
    CAST({sql_string_literal(parent_run_id)} AS VARCHAR) AS source_run_id,
    CAST({sql_string_literal(curated_run_id)} AS VARCHAR) AS curated_run_id,
    {_ts_expr('source_system_mod')} AS source_system_mod,
    year({_ts_expr('source_system_mod')}) AS year,
    month({_ts_expr('source_system_mod')}) AS month,
    day({_ts_expr('source_system_mod')}) AS day
FROM (
    VALUES
    {rows_sql}
) AS staged_input(loan_id, payment_amount, payment_due_date, payment_posted_at, source_system_mod)
"""


def _insert_loan_status_history(*, rows_sql: str, parent_run_id: str, curated_run_id: str) -> str:
    """
    Return the SQL statement responsible for inserting loan status history records
    into the `loan_status_history` silver table.
    """
    return f"""
INSERT INTO lakehouse.silver.loan_status_history
SELECT
    CAST(loan_id AS VARCHAR) AS loan_id,
    CAST(status_code AS VARCHAR) AS status_code,
    {_ts_expr('status_at')} AS status_at,
    CAST({sql_string_literal(parent_run_id)} AS VARCHAR) AS source_run_id,
    CAST({sql_string_literal(curated_run_id)} AS VARCHAR) AS curated_run_id,
    {_ts_expr('source_system_mod')} AS source_system_mod,
    year({_ts_expr('source_system_mod')}) AS year,
    month({_ts_expr('source_system_mod')}) AS month,
    day({_ts_expr('source_system_mod')}) AS day
FROM (
    VALUES
    {rows_sql}
) AS staged_input(loan_id, status_code, status_at, source_system_mod)
"""


def _insert_fact_commission_adjustment(*, rows_sql: str, parent_run_id: str, curated_run_id: str) -> str:
    """
    Return the SQL statement responsible for inserting Excel commission adjustments
    into the `fact_commission_adjustment` silver table.
    """
    return f"""
INSERT INTO lakehouse.silver.fact_commission_adjustment
SELECT
    CAST(advisor_id AS VARCHAR) AS advisor_id,
    CAST(adjustment_amount AS DECIMAL(18, 2)) AS adjustment_amount,
    CAST(adjustment_reason AS VARCHAR) AS adjustment_reason,
    CAST(adjustment_date AS DATE) AS adjustment_date,
    CAST(currency AS VARCHAR) AS currency,
    CAST({sql_string_literal(parent_run_id)} AS VARCHAR) AS source_run_id,
    CAST({sql_string_literal(curated_run_id)} AS VARCHAR) AS curated_run_id,
    current_timestamp AS source_system_mod,
    year(CAST(adjustment_date AS DATE)) AS year,
    month(CAST(adjustment_date AS DATE)) AS month,
    day(CAST(adjustment_date AS DATE)) AS day
FROM (
    VALUES
    {rows_sql}
) AS staged_input(advisor_id, adjustment_amount, adjustment_reason, adjustment_date, currency)
"""


def merge_into_silver(state: dict[str, Any]) -> dict[str, Any]:
    """
    This function performs the merge/insert operations to update the silver tables
    based on the masked rows produced in the previous masking step. It constructs
    the appropriate SQL statements based on the silver domain and executes them
    using a Trino cursor.
    """
    silver_domain = str(state.get("silver_domain") or "")
    masked_rows = list(state.get("masked_rows") or [])
    merge_stats: dict[str, int] = {"inserted": 0, "updated": 0, "closed": 0}

    # Check if there are any masked rows to process. If not, log a message and return early with the current state and empty merge stats.
    if not masked_rows:
        logger.info("no rows available for domain=%s; skipping merge/insert", silver_domain)
        return {**state, "merge_stats": merge_stats}

    # Merge Salesforce opportunities into the silver `dim_opportunity` table
    if silver_domain == "salesforce_opportunity":
        rows_sql = _build_values(
            masked_rows,
            [
                ("opportunity_id", "str"),
                ("account_id_token", "str"),
                ("name", "str"),
                ("stage_name", "str"),
                ("amount", "str"),
                ("close_date", "str"),
                ("is_won", "bool"),
                ("is_closed", "bool"),
                ("source_system_mod", "str"),
            ],
        )

        sql = _merge_opportunity(
            rows_sql=rows_sql,
            parent_run_id=state["parent_run_id"],
            curated_run_id=state["curated_run_id"],
        )

    # Merge Salesforce accounts into the silver `dim_account` table
    elif silver_domain == "salesforce_account":
        rows_sql = _build_values(
            masked_rows,
            [
                ("account_id_token", "str"),
                ("name", "str"),
                ("industry", "str"),
                ("annual_revenue", "str"),
                ("number_of_employees", "str"),
                ("source_system_mod", "str"),
            ],
        )

        sql = _merge_account(
            rows_sql=rows_sql,
            parent_run_id=state["parent_run_id"],
            curated_run_id=state["curated_run_id"],
        )

    # Merge CDC loan records into the silver `dim_loan` table
    elif silver_domain == "loan":
        rows_sql = _build_values(
            masked_rows,
            [
                ("loan_id", "str"),
                ("account_id", "str"),
                ("status_code", "str"),
                ("principal_balance", "str"),
                ("days_past_due", "str"),
                ("source_system_mod", "str"),
            ],
        )

        sql = _merge_dim_loan(
            rows_sql=rows_sql,
            parent_run_id=state["parent_run_id"],
            curated_run_id=state["curated_run_id"],
        )

    # Merge CDC loan records into the silver `loan_payment` table
    elif silver_domain == "loan_payment":
        rows_sql = _build_values(
            masked_rows,
            [
                ("loan_id", "str"),
                ("payment_amount", "str"),
                ("payment_due_date", "str"),
                ("payment_posted_at", "str"),
                ("source_system_mod", "str"),
            ],
        )

        sql = _insert_fact_loan_payment(
            rows_sql=rows_sql,
            parent_run_id=state["parent_run_id"],
            curated_run_id=state["curated_run_id"],
        )

        merge_stats["inserted"] = len(masked_rows)

    # Insert CDC loan status history records into the silver `loan_status_history` table
    elif silver_domain == "loan_status_history":
        rows_sql = _build_values(
            masked_rows,
            [
                ("loan_id", "str"),
                ("status_code", "str"),
                ("status_at", "str"),
                ("source_system_mod", "str"),
            ],
        )

        sql = _insert_loan_status_history(
            rows_sql=rows_sql,
            parent_run_id=state["parent_run_id"],
            curated_run_id=state["curated_run_id"],
        )

        merge_stats["inserted"] = len(masked_rows)

    # Insert Excel commission adjustments into the silver `fact_commission_adjustment` table
    elif silver_domain == "commission_adjustment":
        rows_sql = _build_values(
            masked_rows,
            [
                ("advisor_id", "str"),
                ("adjustment_amount", "str"),
                ("adjustment_reason", "str"),
                ("adjustment_date", "str"),
                ("currency", "str"),
            ],
        )

        sql = _insert_fact_commission_adjustment(
            rows_sql=rows_sql,
            parent_run_id=state["parent_run_id"],
            curated_run_id=state["curated_run_id"],
        )

        merge_stats["inserted"] = len(masked_rows)

    # Else raise an error since the silver domain is not supported
    else:
        raise ValueError(f"unsupported silver domain {silver_domain!r}")

    _run_sql(sql)
    return {**state, "merge_stats": merge_stats}
