"""Shared Keycloak finance-user resolver for demo endpoints."""

from __future__ import annotations

from config import settings
from services.keycloak_users import FinanceUserResolver, KeycloakConfig

_finance_resolver: FinanceUserResolver | None = None


def resolve_demo_user() -> str:
    """Return a random Keycloak `finance`-role user as the demo uploader."""
    global _finance_resolver
    if _finance_resolver is None:
        _finance_resolver = FinanceUserResolver(
            KeycloakConfig(
                base_url=settings.keycloak_url,
                realm=settings.keycloak_realm,
                client_id=settings.keycloak_demo_service_client_id,
                client_secret=settings.keycloak_demo_service_client_secret,
                finance_role=settings.keycloak_finance_role,
            )
        )
    return _finance_resolver.pick_finance_user()


def local_part(email: str) -> str:
    return email.split("@", 1)[0]
