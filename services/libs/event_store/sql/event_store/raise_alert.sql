INSERT INTO event_store.alert_event (
    run_id, severity, category, summary, details, occurred_at
)
VALUES (
    :run_id,
    :severity,
    :category,
    :summary,
    :details,
    :occurred_at
)
