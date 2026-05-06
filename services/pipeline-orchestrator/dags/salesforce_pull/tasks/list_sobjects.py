"""Task callable for salesforce_incremental_pull.list_sobjects."""

from __future__ import annotations

from salesforce_pull.common import _configured_sobjects


def list_sobjects() -> list[str]:
    """
    List the Salesforce objects configured for incremental pull.
    """
    return list(_configured_sobjects())
