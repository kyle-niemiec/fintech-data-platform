"""
Envelope model for all Redpanda platform events.

Conforms to docs/event-contracts.md. The envelope is the wire shape written
to Redpanda and persisted (as `event_log.payload` is the `payload` field only)
to the event store. Hash is over the canonical form of `payload`.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventSource(str, Enum):
    excel = "excel"
    cdc = "cdc"
    salesforce = "salesforce"
    orchestration = "orchestration"
    notification = "notification"


class PipelineClass(str, Enum):
    ingestion = "ingestion"
    curated = "curated"


class PipelineName(str, Enum):
    excel_ingestion = "excel_ingestion"
    cdc_ingestion = "cdc_ingestion"
    cdc_bronze_write = "cdc_bronze_write"
    salesforce_ingestion = "salesforce_ingestion"
    curated_promotion = "curated_promotion"


SCHEMA_VERSION = "v1"
_HASH_PREFIX = "sha256-"


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    """
    Deterministic sha256 of payload. Stable across dict ordering.
    """
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )

    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{_HASH_PREFIX}{digest}"


def _json_default(value: Any) -> Any:
    """
    JSON serializer for non-standard types in payloads. Must be deterministic.
    """
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    if isinstance(value, UUID):
        return str(value)

    raise TypeError(f"Unserializable value for payload hashing: {type(value).__name__}")


class Envelope(BaseModel):
    """
    Envelope model for all Redpanda platform events.
    """
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    source: EventSource
    run_id: UUID
    pipeline_class: PipelineClass
    pipeline_name: PipelineName
    parent_run_id: Optional[UUID] = None
    trigger_event_ref: str
    trace_id: UUID
    occurred_at: datetime
    schema_version: str = SCHEMA_VERSION
    payload_hash: str
    payload: dict[str, Any]


    @field_validator("occurred_at")
    @classmethod
    def _require_tz(cls, value: datetime) -> datetime:
        """
        Validate that occurred_at is timezone-aware (UTC expected). Convert to
        UTC if needed.
        """
        if value.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware (UTC expected)")

        return value.astimezone(timezone.utc)


    @field_validator("trigger_event_ref")
    @classmethod
    def _non_empty_ref(cls, value: str) -> str:
        """
        Validate that trigger_event_ref is non-empty. We allow arbitrary strings
        here, but empty would be unhelpful.
        """
        if not value.strip():
            raise ValueError("trigger_event_ref must not be empty")

        return value


    @field_validator("payload_hash")
    @classmethod
    def _well_formed_hash(cls, value: str) -> str:
        """
        Validate that payload_hash is well-formed (sha256-<64 hex chars>).
        """
        if not value.startswith(_HASH_PREFIX) or len(value) != len(_HASH_PREFIX) + 64:
            raise ValueError("payload_hash must be sha256-<64 hex chars>")

        return value


    @classmethod
    def build(
        cls,
        *,
        event_type: str,
        source: EventSource,
        run_id: UUID,
        pipeline_class: PipelineClass,
        pipeline_name: PipelineName,
        trigger_event_ref: str,
        trace_id: UUID,
        payload: dict[str, Any],
        parent_run_id: Optional[UUID] = None,
        occurred_at: Optional[datetime] = None,
        event_id: Optional[UUID] = None,
    ) -> "Envelope":
        """
        Build an Envelope, computing event_id, occurred_at, and payload_hash if
        not provided.
        """
        return cls(
            event_id=event_id or uuid4(),
            event_type=event_type,
            source=source,
            run_id=run_id,
            pipeline_class=pipeline_class,
            pipeline_name=pipeline_name,
            parent_run_id=parent_run_id,
            trigger_event_ref=trigger_event_ref,
            trace_id=trace_id,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            payload_hash=canonical_payload_hash(payload),
            payload=payload,
        )

    def to_wire(self) -> bytes:
        """
        Serialize the envelope to bytes for writing to Redpanda. The payload is
        included in the JSON, but the hash is pre-computed and must be correct.
        """
        return self.model_dump_json(by_alias=False).encode("utf-8")
