"""
Excel raw->bronze writer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
import logging
from typing import Any, Callable, ContextManager, Protocol
from urllib.parse import urlparse
from uuid import UUID

import pandas as pd

from meridian.libs.redpanda_events.envelope import Envelope, EventSource, PipelineClass, PipelineName
from meridian.libs.event_store import PgEventStore

TOPIC_RAW_READY = "ingest.excel.raw.ready.v1"
TOPIC_BRONZE_READY = "ingest.excel.bronze.ready.v1"

TRANSFORM_ID = "excel_to_parquet"
TRANSFORM_VERSION = "v1"

logger = logging.getLogger(__name__)


class RetryableFinalizationError(RuntimeError):
    """
    Raised when bronze-ready publish/write succeeded but event-store finalization failed.
    """


def split_s3_uri(uri: str) -> tuple[str, str]:
    """
    Parse an S3 URI into bucket and key components and validate them.
    """
    parsed = urlparse(uri)

    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"invalid s3 uri: {uri}")

    return parsed.netloc, parsed.path.lstrip("/")


def raw_uri_to_bronze_uri(raw_uri: str) -> str:
    """
    Convert a raw S3 URI to the corresponding bronze S3 URI
    by replacing the "raw/source=excel/" prefix with "bronze/source=excel/",
    and changing the file extension from .xlsx or .xlsm to .parquet.
    """
    bucket, key = split_s3_uri(raw_uri)

    if not key.startswith("raw/source=excel/"):
        raise ValueError(f"raw uri is not excel raw path: {raw_uri}")

    bronze_key = key.replace("raw/source=excel/", "bronze/source=excel/", 1)

    if bronze_key.endswith(".xlsx"):
        bronze_key = bronze_key[: -len(".xlsx")] + ".parquet"
    elif bronze_key.endswith(".xlsm"):
        bronze_key = bronze_key[: -len(".xlsm")] + ".parquet"
    else:
        bronze_key = f"{bronze_key}.parquet"

    return f"s3://{bucket}/{bronze_key}"


class ObjectStore(Protocol):
    """
    Protocol for an object store client that can read and write bytes to URIs.
    """
    def read_uri(self, uri: str) -> bytes: ...
    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None: ...


class Converter(Protocol):
    """
    Protocol for a converter that can transform Excel bytes to Parquet bytes, along with
    metadata about the transformation.
    """
    def to_parquet(self, xlsx_bytes: bytes) -> tuple[bytes, int, str]: ...


class EventEmitter(Protocol):
    """
    Protocol for an event emitter that can produce events to a topic and return
    the partition and offset of the produced event.
    """
    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]: ...


class PandasParquetConverter:
    """
    Converter implementation that uses pandas to read Excel bytes and write Parquet
    bytes. The schema fingerprint is generated from the column names and data
    types of the DataFrame.
    """


    def to_parquet(self, xlsx_bytes: bytes) -> tuple[bytes, int, str]:
        """
        Convert Excel bytes to Parquet bytes, and return the Parquet bytes, record count,
        and a schema fingerprint.
        """
        df = pd.read_excel(io.BytesIO(xlsx_bytes), engine="openpyxl")
        signature = "|".join(f"{name}:{dtype}" for name, dtype in zip(df.columns, df.dtypes))
        schema_fingerprint = "sha256-" + hashlib.sha256(signature.encode("utf-8")).hexdigest()
        out = io.BytesIO()
        df.to_parquet(out, index=False, engine="pyarrow")

        return out.getvalue(), int(len(df.index)), schema_fingerprint


@dataclass
class ExcelBronzeWriter:
    store: ObjectStore
    converter: Converter
    producer: EventEmitter
    db_connection_factory: Callable[[], ContextManager[Any]]
    kms_key_id: str

    def handle_raw_ready(self, envelope_dict: dict[str, Any]) -> bool:
        """
        Handle a raw ready event by reading the Excel bytes from the raw URI, converting
        them to Parquet bytes, writing the Parquet bytes to the bronze URI, and emitting
        a bronze ready event.
        """
        run_id_str = str(envelope_dict["run_id"])
        trace_id_str = str(envelope_dict["trace_id"])
        trigger_event_ref = str(envelope_dict["trigger_event_ref"])
        payload = envelope_dict.get("payload") or {}
        run_id = UUID(run_id_str)
        trace_id = UUID(trace_id_str)

        try:
            raw_uri = (payload.get("output_uris") or [None])[0]

            if not raw_uri:
                raise ValueError("raw.ready payload missing output_uris[0]")

            # Read the Excel bytes from the raw URI
            xlsx_bytes = self.store.read_uri(raw_uri)
            parquet_bytes, record_count, schema_fingerprint = self.converter.to_parquet(xlsx_bytes)
            bronze_uri = raw_uri_to_bronze_uri(raw_uri)

            # Write the Parquet bytes to the bronze URI
            self.store.write_uri(
                bronze_uri,
                parquet_bytes,
                content_type="application/octet-stream",
                kms_key_id=self.kms_key_id,
            )

            # Build the bronze ready event envelope for Redpanda
            bronze_envelope = Envelope.build(
                event_type=TOPIC_BRONZE_READY,
                source=EventSource.excel,
                run_id=run_id,
                pipeline_class=PipelineClass.ingestion,
                pipeline_name=PipelineName.excel_ingestion,
                trigger_event_ref=trigger_event_ref,
                trace_id=trace_id,
                payload={
                    "message": f"Excel raw transformed to bronze parquet: {bronze_uri}",
                    "stage": "bronze",
                    "format": "parquet",
                    "input_uris": [raw_uri],
                    "output_uris": [bronze_uri],
                    "record_count": record_count,
                    "parquet_schema_fingerprint": schema_fingerprint,
                    "transform_id": TRANSFORM_ID,
                    "transform_version": TRANSFORM_VERSION,
                },
            )

            partition, offset = self.producer.produce(TOPIC_BRONZE_READY, bronze_envelope, key=run_id_str)

            try:
                # Write the bronze ready event to the event store
                with self.db_connection_factory() as db:
                    with db.begin():
                        PgEventStore.append_event(
                            db,
                            bronze_envelope,
                            topic=TOPIC_BRONZE_READY,
                            partition=partition,
                            kafka_offset=offset,
                        )

                        PgEventStore.close_run(db, run_id, status="completed")
            except Exception as exc:
                raise RetryableFinalizationError(
                    f"bronze ready published but finalization failed for run_id={run_id}"
                ) from exc

            return True
        except RetryableFinalizationError:
            raise
        except Exception as exc:
            raw_uri = (payload.get("output_uris") or [None])[0]

            try:
                with self.db_connection_factory() as db:
                    with db.begin():
                        PgEventStore.raise_alert(
                            db,
                            run_id=run_id,
                            severity="high",
                            category="excel_bronze_write_failed",
                            summary="Excel bronze write failed",
                            details={
                                "error": str(exc),
                                "raw_uri": raw_uri,
                            },
                            occurred_at=datetime.now(timezone.utc),
                        )

                        PgEventStore.close_run(db, run_id, status="failed")
            except Exception:
                # Terminal processing failures still return non-success so offsets can advance.
                logger.exception("failed to persist excel_bronze_write_failed alert run_id=%s", run_id)
            return False
