SELECT cursor_ts, cursor_id
FROM event_store.sf_cursor_checkpoint
WHERE sobject = :sobject
ORDER BY recorded_at DESC
LIMIT 1
