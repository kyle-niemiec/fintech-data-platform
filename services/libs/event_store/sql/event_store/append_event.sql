INSERT INTO event_store.event_log (
    event_id, run_id, event_type, topic, partition, kafka_offset,
    occurred_at, trace_id, payload, payload_hash, schema_version
)
VALUES (
    :event_id,
    :run_id,
    :event_type,
    :topic,
    :partition,
    :kafka_offset,
    :occurred_at,
    :trace_id,
    :payload,
    :payload_hash,
    :schema_version
)
ON CONFLICT (topic, partition, kafka_offset, occurred_at) DO NOTHING
RETURNING event_id
