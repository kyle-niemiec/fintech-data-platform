INSERT INTO event_store.sf_cursor_checkpoint (
    run_id, sobject, cursor_ts, cursor_id,
    kafka_partition, offset_start, offset_end, record_count
)
VALUES (
    :run_id,
    :sobject,
    :cursor_ts,
    :cursor_id,
    :kafka_partition,
    :offset_start,
    :offset_end,
    :record_count
)
