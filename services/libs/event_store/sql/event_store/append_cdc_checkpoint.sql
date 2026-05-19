INSERT INTO event_store.cdc_checkpoint (
    run_id, source_table, lsn_start, lsn_end,
    kafka_partition, offset_start, offset_end, record_count
)
VALUES (
    :run_id,
    :source_table,
    :lsn_start,
    :lsn_end,
    :kafka_partition,
    :offset_start,
    :offset_end,
    :record_count
)
