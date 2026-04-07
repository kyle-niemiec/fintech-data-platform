from enum import Enum

"""
The enum for the set of possible ingestion sources.
"""
class IngestionSource(str, Enum):
    excel_upload = "excel_upload"
    salesforce_crm = "salesforce_crm"
    transaction_cdc = "transaction_cdc"

"""
The enum for the set of possible ingestion statuses.
"""
class IngestionStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
