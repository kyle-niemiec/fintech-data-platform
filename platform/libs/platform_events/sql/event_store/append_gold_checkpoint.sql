INSERT INTO event_store.gold_checkpoint (
    run_id, parent_run_id, metric,
    input_uris, output_table, output_uris, record_count
)
VALUES (
    :run_id,
    :parent_run_id,
    :metric,
    :input_uris,
    :output_table,
    :output_uris,
    :record_count
)
