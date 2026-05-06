"""Task callable for excel_validation.validate."""

from __future__ import annotations

from typing import Any

from excel_validation.common import CONTRACTS_ROOT, _b64_decode


def validate(downloaded: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the downloaded Excel payload against the specified contract and
    return the validation results along with the original downloaded metadata.
    """
    from libs.excel_validation import load_contract, load_workbook, validate_dataframe

    contract = load_contract(CONTRACTS_ROOT / f"{downloaded['schema_contract_id']}.json")
    payload = _b64_decode(downloaded["_payload_b64"])
    df = load_workbook(payload, sheet_name=contract.sheet_name)
    result = validate_dataframe(df, contract)

    return {
        **downloaded,
        "passed": result.passed,
        "row_count": result.row_count,
        "errors": result.errors_as_list(),
        "contract_id": contract.contract_id,
    }
