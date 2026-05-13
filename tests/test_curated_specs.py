"""Unit coverage for config-driven curated routing/spec resolution."""

from __future__ import annotations

from curated_specs import resolve_gold_metric, resolve_silver_spec


def _salesforce_bronze_event(*, sobject: str) -> dict:
    return {
        "event_type": "ingest.salesforce.bronze.ready.v1",
        "run_id": "11111111-1111-1111-1111-111111111111",
        "payload": {
            "stage": "bronze",
            "sobject": sobject,
            "output_uris": ["s3://fintech-lakehouse/bronze/source=salesforce/object=Account/part-0.parquet"],
        },
    }


def test_resolve_silver_spec_for_salesforce_account() -> None:
    spec = resolve_silver_spec(_salesforce_bronze_event(sobject="Account"))
    assert spec is not None
    assert spec.domain == "salesforce_account"
    assert spec.output_table == "lakehouse.silver.dim_account"


def test_resolve_silver_spec_for_salesforce_opportunity() -> None:
    spec = resolve_silver_spec(_salesforce_bronze_event(sobject="Opportunity"))
    assert spec is not None
    assert spec.domain == "salesforce_opportunity"
    assert spec.output_table == "lakehouse.silver.dim_opportunity"


def test_resolve_silver_spec_for_cdc_loan_payment() -> None:
    spec = resolve_silver_spec(
        {
            "event_type": "cdc.oltp.bronze.ready.v1",
            "run_id": "11111111-1111-1111-1111-111111111111",
            "payload": {
                "stage": "bronze",
                "source_table": "trading.loan_payment",
                "output_uris": ["s3://fintech-lakehouse/bronze/source=cdc/table=trading.loan_payment/part-0.parquet"],
            },
        }
    )
    assert spec is not None
    assert spec.domain == "loan_payment"
    assert spec.output_table == "lakehouse.silver.fact_loan_payment"


def test_resolve_silver_spec_for_excel_commission_adjustments() -> None:
    spec = resolve_silver_spec(
        {
            "event_type": "ingest.excel.bronze.ready.v1",
            "run_id": "11111111-1111-1111-1111-111111111111",
            "payload": {
                "stage": "bronze",
                "schema_contract_id": "commission_adjustment_v1",
                "output_uris": ["s3://fintech-lakehouse/bronze/source=excel/part-0.parquet"],
            },
        }
    )
    assert spec is not None
    assert spec.domain == "commission_adjustment"
    assert spec.output_table == "lakehouse.silver.fact_commission_adjustment"


def test_resolve_gold_metric_from_silver_domain() -> None:
    metric = resolve_gold_metric("loan")
    assert metric is not None
    assert metric.metric == "portfolio_health"
    assert metric.output_table == "lakehouse.gold.kpi_portfolio_health"


def test_resolve_gold_metric_returns_none_for_unknown_domain() -> None:
    assert resolve_gold_metric("unknown") is None
