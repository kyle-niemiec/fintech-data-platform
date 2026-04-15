"""Minimal SOQL parser supporting the incremental-pull query shape.

Only the form:
    SELECT <fields> FROM <SObject>
    [WHERE SystemModstamp > <ts-literal>]
    [ORDER BY SystemModstamp ASC, Id ASC]
    [LIMIT <n>]

is supported. All other SOQL features raise SoqlError.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


class SoqlError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedQuery:
    sobject: str
    fields: tuple[str, ...]
    since_ts: Optional[datetime]
    limit: Optional[int]


_SELECT_RE = re.compile(
    r"^\s*SELECT\s+(?P<fields>.+?)\s+FROM\s+(?P<sobject>[A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+WHERE\s+SystemModstamp\s*>\s*(?P<ts>[0-9T:\-\+\.Z]+))?"
    r"(?:\s+ORDER\s+BY\s+SystemModstamp(?:\s+ASC)?(?:\s*,\s*Id(?:\s+ASC)?)?)?"
    r"(?:\s+LIMIT\s+(?P<limit>\d+))?"
    r"\s*$",
    re.IGNORECASE,
)


def parse(query: str) -> ParsedQuery:
    m = _SELECT_RE.match(query.strip())
    if not m:
        raise SoqlError(f"unsupported SOQL: {query!r}")
    fields_raw = m.group("fields")
    fields = tuple(f.strip() for f in fields_raw.split(",") if f.strip())
    if not fields:
        raise SoqlError("SELECT requires at least one field")
    since_ts: Optional[datetime] = None
    if m.group("ts"):
        ts_literal = m.group("ts")
        try:
            since_ts = datetime.fromisoformat(ts_literal.replace("Z", "+00:00"))
        except ValueError as exc:
            raise SoqlError(f"invalid SystemModstamp literal: {ts_literal!r}") from exc
        if since_ts.tzinfo is None:
            since_ts = since_ts.replace(tzinfo=timezone.utc)
    limit = int(m.group("limit")) if m.group("limit") else None
    return ParsedQuery(
        sobject=m.group("sobject"),
        fields=fields,
        since_ts=since_ts,
        limit=limit,
    )
