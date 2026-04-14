"""Excel raw->bronze writer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import io
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import UUID

import pandas as pd
import psycopg

from libs.platform_events.envelope import Envelope, EventSource, PipelineClass, PipelineName
from libs.platform_events.event_store import append_event, close_run, raise_alert

TOPIC_RAW_READY = "ingest.excel.raw.ready.v1"
TOPIC_BRONZE_READY = "ingest.excel.bronze.ready.v1"

TRANSFORM_ID = "excel_to_parquet"
TRANSFORM_VERSION = "v1"


def split_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"invalid s3 uri: {uri}")
    return parsed.netloc, parsed.path.lstrip("/")


def raw_uri_to_bronze_uri(raw_uri: str) -> str:
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
    def read_uri(self, uri: str) -> bytes: ...
    def write_uri(self, uri: str, data: bytes, *, content_type: str, kms_key_id: str) -> None: ...


class Converter(Protocol):
    def to_parquet(self, xlsx_bytes: bytes) -> tuple[bytes, int, str]: ...


class EventEmitter(Protocol):
    def produce(self, topic: str, envelope: Envelope, *, key: str) -> tuple[int, int]: ...


class PandasParquetConverter:
    def to_parquet(self, xlsx_bytes: bytes) -> tuple[bytes, int, str]:
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
    db: psycopg.Connection
    kms_key_id: str

    def handle_raw_ready(self, envelope_dict: dict[str, Any]) -> bool:
        run_id_str = str(envelope_dict["run_id"])
        trace_id_str = str(envelope_dict["trace_id"])
        trigger_event_ref = str(envelope_dict["trigger_event_ref"])
        payload = envelope_dict.get("payload") or {}
        raw_uri = (payload.get("output_uris") or [None])[0]
        if not raw_uri:
            raise ValueError("raw.ready payload missing output_uris[0]")

        run_id = UUID(run_id_str)
        trace_id = UUID(trace_id_str)

        try:
            xlsx_bytes = self.store.read_uri(raw_uri)
            parquet_bytes, record_count, schema_fingerprint = self.converter.to_parquet(xlsx_bytes)
            bronze_uri = raw_uri_to_bronze_uri(raw_uri)
            self.store.write_uri(
                bronze_uri,
                parquet_bytes,
                content_type="application/octet-stream",
                kms_key_id=self.kms_key_id,
            )

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
            with self.db.transaction():
                append_event(
                    self.db,
                    bronze_envelope,
                    topic=TOPIC_BRONZE_READY,
                    partition=partition,
                    kafka_offset=offset,
                )
                close_run(self.db, run_id, status="completed")
            return True
        except Exception as exc:
            with self.db.transaction():
                raise_alert(
                    self.db,
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
                close_run(self.db, run_id, status="failed")
            return False

