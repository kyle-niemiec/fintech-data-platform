"""POST /ui/demo/oltp/transaction — inject one synthetic OLTP transaction.

The inserted row flows through Debezium → fraud scoring → CDC bronze. A
high-risk insert (AAPL > $10k) deterministically raises a high-severity alert
and a risk flag, demonstrating the fraud path on demand. Both the normal and
high-risk paths create a `trading.transaction` row and differ only by shape.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError

from db import get_demo_oltp_engine
from services.cdc_demo import create_demo_transaction

router = APIRouter(prefix="/ui/demo/oltp", tags=["ui-demo"])


class CdcTransactionRequest(BaseModel):
    high_risk: bool = Field(default=False)


class CdcTransactionResponse(BaseModel):
    transaction_id: UUID
    account_id: UUID
    instrument: str
    amount: Decimal
    executed_at: datetime
    high_risk: bool


@router.post(
    "/transaction",
    response_model=CdcTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_demo_transaction(
    payload: CdcTransactionRequest | None = None,
) -> CdcTransactionResponse:
    req = payload or CdcTransactionRequest()

    try:
        txn = create_demo_transaction(get_demo_oltp_engine(), high_risk=req.high_risk)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OLTP write failed: {exc}",
        ) from exc

    return CdcTransactionResponse(
        transaction_id=txn.transaction_id,
        account_id=txn.account_id,
        instrument=txn.instrument,
        amount=txn.amount,
        executed_at=txn.executed_at,
        high_risk=txn.high_risk,
    )
