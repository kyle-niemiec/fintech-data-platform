from __future__ import annotations

from typing import Any

import pendulum
from airflow.sdk import DAG, task

from salesforce_pull.common import default_args
from salesforce_pull.tasks.list_sobjects import list_sobjects as list_sobjects_task
from salesforce_pull.tasks.pull_sobject import pull_sobject as pull_sobject_task

"""Salesforce incremental-pull DAG.

Scheduled hourly. For each configured SObject:
  1. Reads the latest cursor from event_store.sf_cursor_checkpoint.
  2. Obtains a short-lived bearer token from the (mock) Salesforce token endpoint.
  3. Paginates a SOQL SELECT ... WHERE SystemModstamp > :cursor ORDER BY 
     SystemModstamp, Id query.
  4. Writes each response page as JSON to MinIO
     raw/source=salesforce/object=.../page-N.json.
  5. Opens a `salesforce_ingestion` pipeline_run, emits
     ingest.salesforce.raw.ready.v1, and leaves the run in 'running' state. The
     salesforce_bronze_writer will append the bronze_ready event, record the
     cursor checkpoint, and close the run.
"""
with DAG(
    dag_id="salesforce_incremental_pull",
    description="Incremental pull from (mock) Salesforce per SObject every 15 minutes.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    schedule="*/15 * * * *",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=False,
    tags=["salesforce", "ingestion"],
) as incremental_pull_dag:

    @task(task_id="list_sobjects")
    def list_sobjects() -> list[str]:
        return list_sobjects_task()

    @task(task_id="pull_sobject", map_index_template="{{ task.op_kwargs.get('sobject', '') }}")
    def pull_sobject(sobject: str, **context) -> dict[str, Any]:
        return pull_sobject_task(sobject=sobject, context=context)

    sobjects = list_sobjects()
    pull_sobject.expand(sobject=sobjects)
