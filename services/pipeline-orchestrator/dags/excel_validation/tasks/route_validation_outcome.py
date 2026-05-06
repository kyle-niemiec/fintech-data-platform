"""Branch callable for excel_validation.branch."""

from __future__ import annotations


def route_validation_outcome(ti) -> str:
    """
    Route to the appropriate branch based on the outcome of the validation.
    """
    validated = ti.xcom_pull(task_ids="validate")
    return "write_raw" if validated["passed"] else "write_quarantine"
