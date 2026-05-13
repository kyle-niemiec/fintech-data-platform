"""Config-driven curated routing and transform metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SilverSpec:
    domain: str
    output_table: str
    transform_id: str


@dataclass(frozen=True)
class GoldMetricSpec:
    metric: str
    output_table: str
    transform_id: str


_SILVER_BY_SALESFORCE_OBJECT: dict[str, SilverSpec] = {
    "Opportunity": SilverSpec(
        domain="salesforce_opportunity",
        output_table="lakehouse.silver.dim_opportunity",
        transform_id="silver_curated_promotion_salesforce_opportunity",
    ),
    "Account": SilverSpec(
        domain="salesforce_account",
        output_table="lakehouse.silver.dim_account",
        transform_id="silver_curated_promotion_salesforce_account",
    ),
}

_SILVER_BY_CDC_TABLE: dict[str, SilverSpec] = {
    "trading.loan": SilverSpec(
        domain="loan",
        output_table="lakehouse.silver.dim_loan",
        transform_id="silver_curated_promotion_dim_loan",
    ),
    "trading.loan_payment": SilverSpec(
        domain="loan_payment",
        output_table="lakehouse.silver.fact_loan_payment",
        transform_id="silver_curated_promotion_fact_loan_payment",
    ),
    "trading.loan_status_history": SilverSpec(
        domain="loan_status_history",
        output_table="lakehouse.silver.loan_status_history",
        transform_id="silver_curated_promotion_loan_status_history",
    ),
}

_SILVER_EXCEL_COMMISSION = SilverSpec(
    domain="commission_adjustment",
    output_table="lakehouse.silver.fact_commission_adjustment",
    transform_id="silver_curated_promotion_fact_commission_adjustment",
)

_GOLD_BY_DOMAIN: dict[str, GoldMetricSpec] = {
    "salesforce_opportunity": GoldMetricSpec(
        metric="pipeline_conversion",
        output_table="lakehouse.gold.kpi_pipeline_conversion",
        transform_id="gold_curated_aggregation_pipeline_conversion",
    ),
    "loan": GoldMetricSpec(
        metric="portfolio_health",
        output_table="lakehouse.gold.kpi_portfolio_health",
        transform_id="gold_curated_aggregation_portfolio_health",
    ),
    "loan_payment": GoldMetricSpec(
        metric="payment_performance",
        output_table="lakehouse.gold.kpi_payment_performance",
        transform_id="gold_curated_aggregation_payment_performance",
    ),
    "commission_adjustment": GoldMetricSpec(
        metric="commission_economics",
        output_table="lakehouse.gold.kpi_commission_economics",
        transform_id="gold_curated_aggregation_commission_economics",
    ),
}


def resolve_silver_spec(envelope: dict[str, Any]) -> SilverSpec | None:
    """
    Resolve the SilverSpec for a given event envelope.
    This function inspects the event type and payload of the envelope to determine which SilverSpec applies.
    It supports multiple event types and payload structures to accommodate different data sources.
    """
    event_type = str(envelope.get("event_type") or "")
    payload = envelope.get("payload") or {}

    if event_type == "ingest.salesforce.bronze.ready.v1":
        object_name = str(payload.get("object_name") or payload.get("sobject") or "")
        return _SILVER_BY_SALESFORCE_OBJECT.get(object_name)

    if event_type == "cdc.oltp.bronze.ready.v1":
        source_table = str(payload.get("source_table") or "")
        return _SILVER_BY_CDC_TABLE.get(source_table)

    if event_type == "ingest.excel.bronze.ready.v1":
        schema_contract_id = str(payload.get("schema_contract_id") or "")
        if schema_contract_id in ("commission_adjustment_v1", "payroll_v1", ""):
            return _SILVER_EXCEL_COMMISSION
        return None

    return None


def resolve_gold_metric(silver_domain: str) -> GoldMetricSpec | None:
    """
    Resolve the GoldMetricSpec for a given silver domain.
    """
    return _GOLD_BY_DOMAIN.get(silver_domain)

