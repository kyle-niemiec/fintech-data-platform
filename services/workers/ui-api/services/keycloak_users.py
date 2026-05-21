"""Resolve demo "finance" actor identities from Keycloak at runtime.

The Excel demo uploader is a randomly selected Keycloak user holding the
`finance` realm role (no human auth in demo mode). The internal
`meridian-demo-service` confidential client authenticates via the
client-credentials grant, and the Admin REST API lists the users in that role.

This deliberately replaces any static/hardcoded finance-user list: if Keycloak
cannot be reached or returns no finance users, resolution fails (the caller
surfaces 503) rather than falling back to stale data.

HTTP is done with the standard library (`urllib`) so the query API gains no new
dependency; the transport is injectable so the resolver is unit-testable
without a live Keycloak.
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


class KeycloakError(RuntimeError):
    """Raised when finance users cannot be resolved from Keycloak."""


@dataclass(frozen=True)
class KeycloakConfig:
    base_url: str
    realm: str
    client_id: str
    client_secret: str
    finance_role: str


class HttpTransport(Protocol):
    def post_form(self, url: str, *, data: dict[str, str]) -> Any: ...
    def get_json(self, url: str, *, bearer: str) -> Any: ...


class UrllibTransport:
    """Dependency-free HTTP transport over the standard library."""

    def __init__(self, *, timeout: float = 5.0):
        self._timeout = timeout

    def post_form(self, url: str, *, data: dict[str, str]) -> Any:
        body = urllib.parse.urlencode(data).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        return self._read_json(req)

    def get_json(self, url: str, *, bearer: str) -> Any:
        req = urllib.request.Request(
            url, headers={"Authorization": f"Bearer {bearer}"}, method="GET"
        )
        return self._read_json(req)

    def _read_json(self, req: urllib.request.Request) -> Any:
        try:
            with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise KeycloakError(str(exc)) from exc


class FinanceUserResolver:
    """Pick a random finance-role username, with a short-lived user-list cache."""

    def __init__(
        self,
        config: KeycloakConfig,
        *,
        transport: HttpTransport | None = None,
        rng: random.Random | None = None,
        clock=time.monotonic,
        cache_ttl_seconds: float = 300.0,
    ):
        self._config = config
        self._transport = transport or UrllibTransport()
        self._rng = rng or random.Random()
        self._clock = clock
        self._cache_ttl = cache_ttl_seconds
        self._cached_users: list[str] | None = None
        self._cache_expires_at: float = 0.0

    def pick_finance_user(self) -> str:
        users = self._finance_usernames()
        if not users:
            raise KeycloakError(
                f"no users hold the '{self._config.finance_role}' role"
            )
        return self._rng.choice(users)

    def _finance_usernames(self) -> list[str]:
        now = self._clock()
        if self._cached_users is not None and now < self._cache_expires_at:
            return self._cached_users
        token = self._fetch_token()
        users = self._fetch_role_users(token)
        self._cached_users = users
        self._cache_expires_at = now + self._cache_ttl
        return users

    def _fetch_token(self) -> str:
        if not self._config.client_secret:
            raise KeycloakError("demo service client secret is not configured")
        url = f"{self._base}/realms/{self._realm}/protocol/openid-connect/token"
        payload = self._transport.post_form(
            url,
            data={
                "grant_type": "client_credentials",
                "client_id": self._config.client_id,
                "client_secret": self._config.client_secret,
            },
        )
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not token:
            raise KeycloakError("token response missing access_token")
        return token

    def _fetch_role_users(self, token: str) -> list[str]:
        role = urllib.parse.quote(self._config.finance_role, safe="")
        url = f"{self._base}/admin/realms/{self._realm}/roles/{role}/users"
        payload = self._transport.get_json(url, bearer=token)
        if not isinstance(payload, list):
            raise KeycloakError("unexpected role-users response shape")
        usernames: list[str] = []
        for user in payload:
            if not isinstance(user, dict):
                continue
            name = user.get("username") or user.get("email")
            if isinstance(name, str) and name.strip():
                usernames.append(name.strip())
        return usernames

    @property
    def _base(self) -> str:
        return self._config.base_url.rstrip("/")

    @property
    def _realm(self) -> str:
        return urllib.parse.quote(self._config.realm, safe="")
