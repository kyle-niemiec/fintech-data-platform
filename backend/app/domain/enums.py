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

"""
The enum for the set of possible artifact lakehouse stages.
"""
class ArtifactStage(str, Enum):
    landing = "landing"
    raw = "raw"
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    quarantine = "quarantine"

"""
The enum for the set of possible artifact file formats.
"""
class ArtifactFormat(str, Enum):
    csv = "csv"
    json = "json"
    parquet = "parquet"
    xlsx = "xlsx"
