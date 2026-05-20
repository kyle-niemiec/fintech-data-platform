"""Excel upload scanner: MIME/size gating + ClamAV INSTREAM scan.

Pure logic lives here with all side-effect clients injected. The Kafka
consumer loop in `main.py` wires a real clamd socket, MinIO client,
Redpanda producer, and psycopg connection.

Event flow per received MinIO S3 notification:
1. Parse record -> UploadedObject
2. Open pipeline_run (idempotent on trigger_event_ref)
3. Append `ingest.excel.uploaded.v1` to event-store
4. Size gate -> on fail: emit scanned.fail with reason=size_exceeded
5. MIME gate -> on fail: emit scanned.fail with reason=content_type_rejected
6. ClamAV INSTREAM -> on FOUND: emit scanned.fail with reason=malware
7. Otherwise: emit scanned.pass
All scanned events are both produced to Redpanda AND appended to the event store.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, BinaryIO, Callable, ContextManager, Optional, Protocol
from urllib.parse import unquote_plus
from uuid import UUID, uuid4


from meridian.libs.redpanda_events.envelope import (
    Envelope,
    EventSource,
    PipelineClass,
    PipelineName,
)
from meridian.libs.event_store import PgEventStore

logger = logging.getLogger(__name__)

DEFAULT_ALLOWED_CONTENT_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel.sheet.macroEnabled.12",
    }
)

XLSX_MAGIC = b"PK\x03\x04"

TOPIC_UPLOADED = "ingest.excel.uploaded.v1"
TOPIC_SCAN_PASS = "ingest.excel.scanned.pass.v1"
TOPIC_SCAN_FAIL = "ingest.excel.scanned.fail.v1"
DEFAULT_SCHEMA_CONTRACT_ID = "payroll_v1"

SCAN_ENGINE = "clamav"


@dataclass(frozen=True)
class UploadedObject:
    """
    Represents an uploaded object extracted from a MinIO S3 notification record.
    """
    bucket: str
    object_key: str
    etag: str
    size_bytes: int
    content_type: str
    uploader_principal: str
    event_time: datetime

    @property
    def trigger_event_ref(self) -> str:
        return f"minio:{self.bucket}:{self.object_key}:{self.etag}"



@dataclass(frozen=True)
class ScanVerdict:
    """
    Represents the result of scanning an uploaded object, including pass/fail and failure reason if applicable.
    """
    passed: bool
    reason: Optional[str] = None
    detail: Optional[str] = None



class ObjectStore(Protocol):
    def stat(self, bucket: str, key: str) -> dict[str, Any]: ...
    def get_stream(self, bucket: str, key: str) -> BinaryIO: ...


class ClamdClient(Protocol):
    def instream(self, stream: BinaryIO) -> dict[str, tuple[str, Optional[str]]]: ...
    def version(self) -> str: ...


class EventEmitter(Protocol):
    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]:
        """Produce to the topic and return (partition, offset)."""


def parse_minio_record(record: dict[str, Any]) -> UploadedObject:
    """
    Translate one `Records[i]` from a MinIO S3 notification.

    Unknown/missing fields raise ValueError — malformed records should
    dead-letter rather than be silently ignored.
    """
    # Build uploaded object values from the record
    try:
        s3 = record["s3"]
        bucket = s3["bucket"]["name"]
        obj = s3["object"]
        object_key = unquote_plus(obj["key"])
        size_bytes = int(obj["size"])
        etag = obj.get("eTag") or obj.get("etag") or ""
        content_type = obj.get("contentType") or obj.get("content-type") or ""

        # TECH-DEBT: uploader needs to be deterministically extracted from the record for proper attribution
        uploader = (
            record.get("userIdentity", {}).get("principalId")
            or record.get("requestParameters", {}).get("principalId")
            or "unknown"
        )

        event_time_str = record.get("eventTime") or datetime.now(timezone.utc).isoformat()
    except KeyError as exc:
        raise ValueError(f"Malformed MinIO S3 notification: missing {exc}") from exc

    try:
        event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Invalid eventTime {event_time_str!r}") from exc

    if not etag:
        raise ValueError(f"MinIO record for {object_key} missing eTag")

    return UploadedObject(
        bucket=bucket,
        object_key=object_key,
        etag=etag,
        size_bytes=size_bytes,
        content_type=content_type,
        uploader_principal=uploader,
        event_time=event_time,
    )


def check_size(obj: UploadedObject, max_bytes: int) -> ScanVerdict:
    """
    Check if the object's size is within the allowed limit.
    """
    if obj.size_bytes > max_bytes:
        return ScanVerdict(
            passed=False,
            reason="size_exceeded",
            detail=f"{obj.size_bytes} > {max_bytes}",
        )

    if obj.size_bytes <= 0:
        return ScanVerdict(passed=False, reason="size_invalid", detail=str(obj.size_bytes))

    return ScanVerdict(passed=True)


def check_mime(obj: UploadedObject, allowed: frozenset[str], *, magic_probe: bytes) -> ScanVerdict:
    """
    Check if the object's content type is allowed and if the magic bytes match expected XLSX signature.
    """
    # Check content type
    if obj.content_type not in allowed:
        return ScanVerdict(
            passed=False,
            reason="content_type_rejected",
            detail=obj.content_type or "<missing>",
        )

    # Simple magic byte check for XLSX files (which are ZIP archives with specific structure).
    if not magic_probe.startswith(XLSX_MAGIC):
        return ScanVerdict(
            passed=False,
            reason="magic_bytes_mismatch",
            detail=magic_probe[:4].hex(),
        )

    return ScanVerdict(passed=True)


def interpret_clamd_result(result: dict[str, tuple[str, Optional[str]]]) -> ScanVerdict:
    """
    ClamAV INSTREAM returns {'stream': ('OK'|'FOUND'|'ERROR', detail)}.
    """
    status, detail = result.get("stream", ("ERROR", "no stream key"))

    if status == "OK":
        return ScanVerdict(passed=True)

    if status == "FOUND":
        return ScanVerdict(passed=False, reason="malware", detail=detail)

    return ScanVerdict(passed=False, reason="scan_error", detail=detail or status)


@dataclass(frozen=True)
class ScannerConfig:
    max_bytes: int = 25 * 1024 * 1024
    allowed_content_types: frozenset[str] = DEFAULT_ALLOWED_CONTENT_TYPES
    scan_engine_version: str = "unknown"


class ExcelScanner:
    """
    Core logic for processing uploaded Excel files: gating and scanning.
    """


    def __init__(
        self,
        *,
        object_store: ObjectStore,
        clamd_client: ClamdClient,
        producer: EventEmitter,
        db_connection_factory: Callable[[], ContextManager[Any]],
        config: ScannerConfig,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        """
        Inject side-effect clients and configuration for testability.
        """
        self._objects = object_store
        self._clamd = clamd_client
        self._producer = producer
        self._db_connection_factory = db_connection_factory
        self._config = config
        self._now = now


    def handle_record(
        self,
        record: dict[str, Any],
        *,
        source_topic: str,
        source_partition: int,
        source_offset: int,
    ) -> None:
        """
        Process one MinIO S3 notification record: parse, open run, emit uploaded event,
        gate/scan, emit scanned event, raise alert if failed.
        """
        # Parse S3 notification
        obj = parse_minio_record(record)

        # Attempt to enrich uploader_principal from object metadata if available, since the
        # record's uploader extraction is best-effort and may be missing/incorrect depending
        # on how the upload was performed.
        #
        # TECH-DEBT: the uploader needs to be deterministically extracted from the record or reliably included in object metadata by the uploader.
        try:
            stat = self._objects.stat(obj.bucket, obj.object_key)
        except Exception as exc:
            logger.warning(
                "failed to stat object for uploader metadata bucket=%s key=%s error=%s",
                obj.bucket,
                obj.object_key,
                exc,
            )
        else:
            metadata_uploader = _extract_uploader_from_stat(stat)

            if metadata_uploader:
                obj = replace(obj, uploader_principal=metadata_uploader)

        run_id = uuid4()
        trace_id = uuid4()

        # Create the event store run and emit the "uploaded" event before gating/scanning
        with self._db_connection_factory() as db:
            with db.begin():
                run_id = PgEventStore.open_run(
                    db,
                    run_id=run_id,
                    pipeline_class=PipelineClass.ingestion,
                    pipeline_name=PipelineName.excel_ingestion,
                    source_system="excel",
                    trigger_type="minio_object_created",
                    trigger_event_ref=obj.trigger_event_ref,
                    initiator=obj.uploader_principal,
                )

                uploaded_env = self._build_uploaded_envelope(obj, run_id, trace_id)

                PgEventStore.append_event(
                    db,
                    uploaded_env,
                    topic=source_topic,
                    partition=source_partition,
                    kafka_offset=source_offset,
                )

        # Run gates and scan
        verdict = self._run_gates_and_scan(obj)
        scanned_env = self._build_scanned_envelope(obj, verdict, run_id, trace_id)
        topic = TOPIC_SCAN_PASS if verdict.passed else TOPIC_SCAN_FAIL
        partition, offset = self._producer.produce(topic, scanned_env, key=str(run_id))

        # Persist the scanned event and raise alert if failed, within the same transaction to ensure consistency between event store and emitted events.
        with self._db_connection_factory() as db:
            with db.begin():
                PgEventStore.append_event(
                    db,
                    scanned_env,
                    topic=topic,
                    partition=partition,
                    kafka_offset=offset,
                )

                # Raise alert for failures with severity based on reason, and close the run with appropriate status
                if not verdict.passed:
                    PgEventStore.raise_alert(
                        db,
                        run_id=run_id,
                        severity="high" if verdict.reason == "malware" else "medium",
                        category="excel_scan_failed",
                        summary=f"Excel upload rejected: {verdict.reason}",
                        details={
                            "object_key": obj.object_key,
                            "reason": verdict.reason,
                            "detail": verdict.detail,
                        },
                    )

                    PgEventStore.close_run(db, run_id, status="scan_failed")

        # Log the result of the scan for observability
        logger.info(
            "scanned object_key=%s verdict=%s reason=%s run_id=%s",
            obj.object_key,
            "pass" if verdict.passed else "fail",
            verdict.reason,
            run_id,
        )


    def _run_gates_and_scan(self, obj: UploadedObject) -> ScanVerdict:
        """
        Run size gate, MIME gate, and ClamAV scan sequentially, returning the first failure verdict or pass if all succeed.
        """
        # Check file size
        size_verdict = check_size(obj, self._config.max_bytes)

        if not size_verdict.passed:
            return size_verdict

        stream = self._objects.get_stream(obj.bucket, obj.object_key)

        # Check MIME type and magic bytes
        try:
            probe = stream.read(4)
            mime_verdict = check_mime(obj, self._config.allowed_content_types, magic_probe=probe)

            if not mime_verdict.passed:
                return mime_verdict
            # re-obtain stream for scan; callers implementing get_stream must
            # return a fresh stream each call.
        finally:
            close = getattr(stream, "close", None)

            if close:
                close()

        scan_stream = self._objects.get_stream(obj.bucket, obj.object_key)

        # Run the ClamAV scan
        try:
            result = self._clamd.instream(scan_stream)
        finally:
            close = getattr(scan_stream, "close", None)

            if close:
                close()

        # Return the interpreted scan result
        return interpret_clamd_result(result)


    def _build_uploaded_envelope(
        self, obj: UploadedObject, run_id: UUID, trace_id: UUID
    ) -> Envelope:
        """
        Build the envelope for the "uploaded" event, which is emitted before gating/scanning.
        """
        return Envelope.build(
            event_type=TOPIC_UPLOADED,
            source=EventSource.excel,
            run_id=run_id,
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.excel_ingestion,
            trigger_event_ref=obj.trigger_event_ref,
            trace_id=trace_id,
            occurred_at=obj.event_time,
            payload={
                "message": f"Excel upload received: {obj.object_key}",
                "stage": "raw",
                "bucket": obj.bucket,
                "object_key": obj.object_key,
                "uploader_principal": obj.uploader_principal,
                "content_type": obj.content_type,
                "size_bytes": obj.size_bytes,
            },
        )


    def _build_scanned_envelope(
        self,
        obj: UploadedObject,
        verdict: ScanVerdict,
        run_id: UUID,
        trace_id: UUID,
    ) -> Envelope:
        """
        Build the envelope for the "scanned" event, which is emitted after gating/scanning with the result.
        """
        event_type = TOPIC_SCAN_PASS if verdict.passed else TOPIC_SCAN_FAIL

        payload = {
            "message": (
                f"Excel upload {obj.object_key} passed scan"
                if verdict.passed
                else f"Excel upload {obj.object_key} rejected: {verdict.reason}"
            ),
            "scan_engine": SCAN_ENGINE,
            "scan_version": self._config.scan_engine_version,
            "scan_result": "pass" if verdict.passed else "fail",
            "failure_reason": verdict.reason,
            "bucket": obj.bucket,
            "object_key": obj.object_key,
            "schema_contract_id": _infer_schema_contract_id(obj.object_key),
            "input_uris": [f"s3://{obj.bucket}/{obj.object_key}"],
        }

        return Envelope.build(
            event_type=event_type,
            source=EventSource.excel,
            run_id=run_id,
            pipeline_class=PipelineClass.ingestion,
            pipeline_name=PipelineName.excel_ingestion,
            trigger_event_ref=obj.trigger_event_ref,
            trace_id=trace_id,
            occurred_at=self._now(),
            payload=payload,
        )


def _extract_uploader_from_stat(stat: dict[str, Any]) -> str | None:
    """
    Attempt to extract uploader principal from object metadata using common keys, case-insensitively.
    """
    metadata = stat.get("metadata")

    if not isinstance(metadata, dict):
        return None

    lowered = {str(k).lower(): v for k, v in metadata.items()}

    # Check common metadata keys for uploader principal, case-insensitively.
    # TECH-DEBT: this is brittle and relies on upstream uploader to set metadata in a consistent way; ideally the uploader would set a well-known metadata key that we can reliably read here.
    for key in (
        "demo-uploader",
        "x-amz-meta-demo-uploader",
        "uploader-principal",
        "x-amz-meta-uploader-principal",
    ):
        value = lowered.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return None


def _infer_schema_contract_id(object_key: str) -> str:
    """
    Finds a schema contract ID based on the object key.
    """
    lowered = object_key.lower()

    if "commission" in lowered:
        return "commission_adjustment_v1"

    return DEFAULT_SCHEMA_CONTRACT_ID


__all__ = [
    "DEFAULT_ALLOWED_CONTENT_TYPES",
    "ExcelScanner",
    "ScanVerdict",
    "ScannerConfig",
    "UploadedObject",
    "check_mime",
    "check_size",
    "interpret_clamd_result",
    "parse_minio_record",
    "TOPIC_UPLOADED",
    "TOPIC_SCAN_PASS",
    "TOPIC_SCAN_FAIL",
]
