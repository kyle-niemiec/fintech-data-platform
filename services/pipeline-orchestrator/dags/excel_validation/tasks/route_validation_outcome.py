from __future__ import annotations


def route_validation_outcome(ti) -> str:
    """
    Callback function for the BranchPythonOperator located in the Excel pipeline.
    Route to the appropriate branch based on the outcome of the validation.
    """
    validated = ti.xcom_pull(task_ids="validate")
    return "write_raw" if validated["passed"] else "write_quarantine"
