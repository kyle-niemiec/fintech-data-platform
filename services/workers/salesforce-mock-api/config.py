from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    api_version: str
    token_ttl_seconds: int
    mutation_interval_seconds: float
    seed_accounts: int
    seed_contacts: int
    seed_opportunities: int
    rng_seed: int
    default_page_size: int

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            client_id=os.environ.get("SALESFORCE_MOCK_CLIENT_ID", "mock-client-id"),
            client_secret=os.environ.get("SALESFORCE_MOCK_CLIENT_SECRET", "mock-client-secret"),
            api_version=os.environ.get("SALESFORCE_MOCK_API_VERSION", "v59.0"),
            token_ttl_seconds=int(os.environ.get("SALESFORCE_MOCK_TOKEN_TTL_SECONDS", "900")),
            mutation_interval_seconds=float(os.environ.get("SALESFORCE_MOCK_MUTATION_INTERVAL_SECONDS", "30")),
            seed_accounts=int(os.environ.get("SALESFORCE_MOCK_SEED_ACCOUNTS", "100")),
            seed_contacts=int(os.environ.get("SALESFORCE_MOCK_SEED_CONTACTS", "300")),
            seed_opportunities=int(os.environ.get("SALESFORCE_MOCK_SEED_OPPORTUNITIES", "150")),
            rng_seed=int(os.environ.get("SALESFORCE_MOCK_RNG_SEED", "42")),
            default_page_size=int(os.environ.get("SALESFORCE_MOCK_DEFAULT_PAGE_SIZE", "200")),
        )
