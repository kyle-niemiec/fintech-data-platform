UPDATE event_store.pipeline_run
SET status = :status,
    completed_at = COALESCE(:completed_at, now())
WHERE run_id = :run_id
