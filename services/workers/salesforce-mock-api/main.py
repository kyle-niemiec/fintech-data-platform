"""Mock Salesforce REST API for the fintech demo stack.

Implements the narrow slice of Salesforce the incremental-pull DAG uses:
- OAuth 2.0 client_credentials token exchange
- SOQL SELECT ... FROM <SObject> WHERE SystemModstamp > :ts ORDER BY SystemModstamp, Id LIMIT N
- Cursor pagination via nextRecordsUrl

Not a full SF emulator; rejects anything outside that shape.
"""

from __future__ import annotations

import base64
import json
import logging
import secrets
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Form, HTTPException, Header, Request
from fastapi.responses import JSONResponse

from config import Settings
from corpus import Corpus, MutationLoop
from soql import SoqlError, parse

logger = logging.getLogger("salesforce_mock")

_SETTINGS: Settings
_CORPUS: Corpus
_MUTATOR: MutationLoop
_TOKENS: dict[str, float] = {}
_TOKENS_LOCK = threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _SETTINGS, _CORPUS, _MUTATOR
    logging.basicConfig(level="INFO")
    _SETTINGS = Settings.from_env()
    _CORPUS = Corpus(
        rng_seed=_SETTINGS.rng_seed,
        seed_accounts=_SETTINGS.seed_accounts,
        seed_contacts=_SETTINGS.seed_contacts,
        seed_opportunities=_SETTINGS.seed_opportunities,
    )
    _MUTATOR = MutationLoop(_CORPUS, _SETTINGS.mutation_interval_seconds)
    _MUTATOR.start()
    logger.info("salesforce_mock ready: api_version=%s seeded corpus", _SETTINGS.api_version)
    try:
        yield
    finally:
        _MUTATOR.stop()


app = FastAPI(title="salesforce-mock", lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.post("/services/oauth2/token")
def oauth_token(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
) -> JSONResponse:
    if grant_type != "client_credentials":
        raise HTTPException(status_code=400, detail={"error": "unsupported_grant_type"})
    if client_id != _SETTINGS.client_id or client_secret != _SETTINGS.client_secret:
        raise HTTPException(status_code=401, detail={"error": "invalid_client"})
    token = secrets.token_urlsafe(24)
    with _TOKENS_LOCK:
        _TOKENS[token] = time.time() + _SETTINGS.token_ttl_seconds
    return JSONResponse(
        {
            "access_token": token,
            "instance_url": "http://salesforce_mock:8080",
            "token_type": "Bearer",
            "issued_at": str(int(time.time() * 1000)),
            "expires_in": _SETTINGS.token_ttl_seconds,
        }
    )


def _require_token(authorization: Optional[str] = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail={"error": "missing_bearer"})
    token = authorization.split(" ", 1)[1].strip()
    with _TOKENS_LOCK:
        exp = _TOKENS.get(token)
        if exp is None or exp < time.time():
            _TOKENS.pop(token, None)
            raise HTTPException(status_code=401, detail={"error": "invalid_or_expired_token"})
    return token


def _encode_cursor(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(token: str) -> dict:
    pad = "=" * (-len(token) % 4)
    return json.loads(base64.urlsafe_b64decode(token + pad).decode())


def _build_page(sobject: str, fields: tuple[str, ...], since_ts: datetime | None, page_size: int) -> dict:
    rows = _CORPUS.query(sobject=sobject, fields=fields, since_ts=since_ts, limit=None)
    total = len(rows)
    first = rows[:page_size]
    done = total <= page_size
    resp: dict = {
        "totalSize": total,
        "done": done,
        "records": first,
    }
    if not done:
        last = first[-1]
        next_since = last["SystemModstamp"]
        cursor = _encode_cursor(
            {"s": sobject, "f": list(fields), "ps": page_size, "since": next_since}
        )
        resp["nextRecordsUrl"] = f"/services/data/{_SETTINGS.api_version}/query/{cursor}"
    return resp


@app.get("/services/data/{version}/query")
def query(
    version: str,
    q: str,
    _token: str = Depends(_require_token),
) -> JSONResponse:
    if version != _SETTINGS.api_version:
        raise HTTPException(status_code=404, detail={"error": "unsupported_api_version"})
    try:
        parsed = parse(q)
    except SoqlError as exc:
        raise HTTPException(status_code=400, detail={"error": "MALFORMED_QUERY", "message": str(exc)})
    if parsed.sobject not in ("Account", "Contact", "Opportunity"):
        raise HTTPException(status_code=404, detail={"error": "INVALID_TYPE", "message": parsed.sobject})
    page_size = parsed.limit or _SETTINGS.default_page_size
    return JSONResponse(_build_page(parsed.sobject, parsed.fields, parsed.since_ts, page_size))


@app.get("/services/data/{version}/query/{cursor}")
def query_next(
    version: str,
    cursor: str,
    _token: str = Depends(_require_token),
) -> JSONResponse:
    if version != _SETTINGS.api_version:
        raise HTTPException(status_code=404, detail={"error": "unsupported_api_version"})
    try:
        payload = _decode_cursor(cursor)
    except Exception:
        raise HTTPException(status_code=400, detail={"error": "INVALID_CURSOR"})
    sobject = payload["s"]
    fields = tuple(payload["f"])
    page_size = int(payload["ps"])
    since_raw = payload["since"]
    since_ts = datetime.fromisoformat(since_raw.replace("Z", "+00:00"))
    if since_ts.tzinfo is None:
        since_ts = since_ts.replace(tzinfo=timezone.utc)
    return JSONResponse(_build_page(sobject, fields, since_ts, page_size))


@app.exception_handler(HTTPException)
async def _sf_error(request: Request, exc: HTTPException) -> JSONResponse:
    body = exc.detail if isinstance(exc.detail, dict) else {"error": str(exc.detail)}
    return JSONResponse([body], status_code=exc.status_code)
