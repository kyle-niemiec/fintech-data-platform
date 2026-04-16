-- SCD2 MERGE for lakehouse.silver.dim_opportunity.
--
-- Parameters interpolated by the DAG before execution:
--   :staged_uri       s3:// location of the DAG-written staging parquet
--   :parent_run_id    UUID of the upstream salesforce_ingestion run
--   :curated_run_id   UUID of this curated_promotion run
--
-- Logic:
--   * Read the masked+normalized staging parquet via Iceberg external table.
--   * Match current rows (is_current = true) by opportunity_id.
--   * If any source-faithful business attribute changed, close the current row
--     (valid_to = source_system_mod, is_current = false) and insert a new
--     current version.
--   * If no match, insert as a new current version.
--
-- The Iceberg connector supports MERGE INTO on v2 tables, and emits row-count
-- stats that the DAG captures after execution via cursor.stats().
MERGE INTO lakehouse.silver.dim_opportunity AS tgt
USING (
    SELECT
        opportunity_id,
        account_id_token,
        name,
        stage_name,
        CAST(amount AS DECIMAL(18, 2)) AS amount,
        CAST(close_date AS DATE) AS close_date,
        is_won,
        is_closed,
        CAST(source_system_mod AS TIMESTAMP(6) WITH TIME ZONE) AS source_system_mod,
        CAST(:parent_run_id AS VARCHAR) AS source_run_id,
        CAST(:curated_run_id AS VARCHAR) AS curated_run_id
    FROM TABLE(
        system.read_parquet(location => :staged_uri)
    )
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
    );
