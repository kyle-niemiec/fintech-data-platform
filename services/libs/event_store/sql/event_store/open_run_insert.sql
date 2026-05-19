INSERT INTO event_store.pipeline_run (
    run_id, pipeline_class, pipeline_name, source_system,
    trigger_type, trigger_event_ref, status, initiator, parent_run_id
)
VALUES (
    :run_id,
    :pipeline_class,
    :pipeline_name,
    :source_system,
    :trigger_type,
    :trigger_event_ref,
    :status,
    :initiator,
    :parent_run_id
)
ON CONFLICT (pipeline_name, trigger_event_ref) DO NOTHING
RETURNING run_id
