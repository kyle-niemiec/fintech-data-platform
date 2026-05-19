SELECT run_id
FROM event_store.pipeline_run
WHERE pipeline_name = :pipeline_name
  AND trigger_event_ref = :trigger_event_ref
