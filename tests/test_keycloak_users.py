"""Unit coverage for runtime Keycloak finance-user resolution.

The resolver is exercised with a fake HTTP transport so no live Keycloak is
needed. Covers selection, user-list caching, email fallback, and the failure
modes that must surface to the caller (which maps them to HTTP 503).
"""

from __future__ import annotations

import random

import pytest

from services.keycloak_users import (
    FinanceUserResolver,
    KeycloakConfig,
    KeycloakError,
)

CFG = KeycloakConfig(
    base_url="http://keycloak:8080",
    realm="meridian",
    client_id="meridian-demo-service",
    client_secret="s3cr3t-value",
    finance_role="finance",
)


class FakeTransport:
    def __init__(self, token_response, users_response):
        self.token_response = token_response
        self.users_response = users_response
        self.post_calls = 0
        self.get_calls = 0

    def post_form(self, url, *, data):
        self.post_calls += 1
        if isinstance(self.token_response, Exception):
            raise self.token_response
        return self.token_response

    def get_json(self, url, *, bearer):
        self.get_calls += 1
        if isinstance(self.users_response, Exception):
            raise self.users_response
        return self.users_response


def test_pick_returns_a_role_user():
    t = FakeTransport({"access_token": "tok"}, [{"username": "a@x"}, {"username": "b@x"}])
    resolver = FinanceUserResolver(CFG, transport=t, rng=random.Random(0))
    assert resolver.pick_finance_user() in {"a@x", "b@x"}
    assert t.post_calls == 1
    assert t.get_calls == 1


def test_caches_user_list_within_ttl():
    t = FakeTransport({"access_token": "tok"}, [{"username": "a@x"}])
    clock = {"t": 1000.0}
    resolver = FinanceUserResolver(
        CFG,
        transport=t,
        rng=random.Random(0),
        clock=lambda: clock["t"],
        cache_ttl_seconds=300,
    )
    resolver.pick_finance_user()
    resolver.pick_finance_user()
    assert t.get_calls == 1  # second call served from cache

    clock["t"] += 301
    resolver.pick_finance_user()
    assert t.get_calls == 2  # refetched after TTL expiry


def test_falls_back_to_email_when_username_absent():
    t = FakeTransport({"access_token": "tok"}, [{"email": "c@x"}])
    resolver = FinanceUserResolver(CFG, transport=t, rng=random.Random(0))
    assert resolver.pick_finance_user() == "c@x"


def test_missing_client_secret_raises():
    cfg = KeycloakConfig(
        base_url="http://keycloak:8080",
        realm="meridian",
        client_id="c",
        client_secret="",
        finance_role="finance",
    )
    resolver = FinanceUserResolver(cfg, transport=FakeTransport({"access_token": "x"}, []))
    with pytest.raises(KeycloakError):
        resolver.pick_finance_user()


def test_empty_role_membership_raises():
    resolver = FinanceUserResolver(CFG, transport=FakeTransport({"access_token": "tok"}, []))
    with pytest.raises(KeycloakError):
        resolver.pick_finance_user()


def test_token_without_access_token_raises():
    resolver = FinanceUserResolver(CFG, transport=FakeTransport({"error": "nope"}, []))
    with pytest.raises(KeycloakError):
        resolver.pick_finance_user()


def test_non_list_users_response_raises():
    resolver = FinanceUserResolver(CFG, transport=FakeTransport({"access_token": "tok"}, {"x": 1}))
    with pytest.raises(KeycloakError):
        resolver.pick_finance_user()


def test_transport_failure_propagates_as_keycloak_error():
    resolver = FinanceUserResolver(CFG, transport=FakeTransport(KeycloakError("down"), []))
    with pytest.raises(KeycloakError):
        resolver.pick_finance_user()
