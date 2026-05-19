INSERT INTO event_store.silver_checkpoint (
    run_id, parent_run_id, silver_domain,
    input_uris, output_table, output_uris,
    record_count, merge_inserted, merge_updated, merge_closed
)
VALUES (
    :run_id,
    :parent_run_id,
    :silver_domain,
    :input_uris,
    :output_table,
    :output_uris,
    :record_count,
    :merge_inserted,
    :merge_updated,
    :merge_closed
)
