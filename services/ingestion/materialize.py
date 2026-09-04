"""M13 — Domain materialization for accepted source rows.

This layer persists an ACCEPTED source row into the authoritative financial
domain (Payment / Refund / Fee / Settlement / BankTransaction) plus the M2
provenance ledger (IngestionRecord with run_id lineage). It is the ONLY place
raw source rows become financial facts.

Safety rules
------------
- Reference existence is checked BEFORE any insert (missing parents become
  row-level REJECTED results — nothing is persisted and nothing is polluted).
- M2 domain rules (refund <= payment + currency match, settlement totals) are
  enforced deterministically for every accepted row.
- Row ids are server-generated (never client-controlled).
- The caller wraps each materialization in a SAVEPOINT so an IntegrityError
  from a concurrent duplicate rolls back only that row and is classified as
  DUPLICATE by the batch service.
"""

from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    BankTransaction,
    Fee,
    IngestionRecord,
    Merchant,
    Order,
    Payment,
    Refund,
    Settlement,
)
from packages.schemas.enums import (
    BankTransactionStatus,
    PaymentStatus,
    RefundStatus,
    SettlementStatus,
)
from services.ingestion.base import (
    validate_refund_domain_rules,
    validate_settlement_totals,
)
from services.ingestion.validation import new_record_id

# Stable row-level error codes for reference / domain failures. These rows are
# REJECTED (safe, auditable) — they never reach the financial domain.
REFERENCED_ENTITY_NOT_FOUND = "REFERENCED_ENTITY_NOT_FOUND"
DOMAIN_RULE_VIOLATION = "DOMAIN_RULE_VIOLATION"


class MaterializationError(Exception):
    """Valid row could not be materialized. Carries a stable row-level code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


async def _resolve_by_ref(
    db: AsyncSession,
    table,
    ref: Optional[dict],
    *,
    provider_column: Any = None,
    provider_value: Optional[str] = None,
):
    """Resolve an entity reference ({'id':...} | {'external_id':...}).

    External-id lookups are scoped by provider when the table carries a
    provider column and the caller provides a provider value, so ids from
    different providers never collide.
    """
    if ref is None:
        return None
    if "id" in ref:
        result = await db.execute(select(table).where(table.id == ref["id"]))
        return result.scalar_one_or_none()
    stmt = select(table).where(table.external_id == ref["external_id"])
    if provider_column is not None and provider_value:
        stmt = stmt.where(provider_column == provider_value)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _require(entity_type: str, label: str, obj) -> Any:
    if obj is None:
        raise MaterializationError(
            REFERENCED_ENTITY_NOT_FOUND,
            f"{entity_type} references {label} that does not exist",
        )
    return obj


async def _materialize_payment(
    db: AsyncSession, run_id: str, payload: dict, raw: dict, row_fingerprint: str
) -> tuple[Payment, IngestionRecord]:
    merchant = await _resolve_by_ref(db, Merchant, payload["merchant_ref"])
    _require("PAYMENT", "merchant", merchant)
    order = await _resolve_by_ref(db, Order, payload["order_ref"])
    _require("PAYMENT", "order", order)

    payment = Payment(
        id=new_record_id("PAYMENT"),
        external_id=payload["external_id"],
        merchant_id=merchant.id,
        order_id=order.id,
        provider=payload["provider"],
        amount=payload["amount"],
        currency=payload["currency"],
        status=payload["status"],
        payment_method_type=payload.get("payment_method_type"),
        processed_at=payload.get("processed_at"),
    )
    record = IngestionRecord(
        id=new_record_id(""),
        provider=payload["provider"],
        external_id=payload["external_id"],
        entity_type="PAYMENT",
        raw_payload=raw,
        fingerprint=row_fingerprint,
        status="PROCESSED",
        run_id=run_id,
    )
    db.add_all([payment, record])
    return payment, record


async def _materialize_refund(
    db: AsyncSession, run_id: str, payload: dict, raw: dict, row_fingerprint: str
) -> tuple[Refund, IngestionRecord]:
    provider = payload["provider"]
    payment = await _resolve_by_ref(
        db, Payment, payload["payment_ref"], provider_column=Payment.provider,
        provider_value=provider,
    )
    payment = _require("REFUND", "payment", payment)
    # M2 domain rule: refund can never exceed the payment or change currency.
    try:
        validate_refund_domain_rules(
            payload["amount"], payment.amount, payload["currency"], payment.currency
        )
    except ValueError as exc:
        raise MaterializationError(DOMAIN_RULE_VIOLATION, str(exc))

    refund = Refund(
        id=new_record_id("REFUND"),
        external_id=payload["external_id"],
        provider=provider,
        merchant_id=payment.merchant_id,
        payment_id=payment.id,
        amount=payload["amount"],
        currency=payload["currency"],
        status=payload["status"],
        reason=payload.get("reason"),
        processed_at=payload.get("processed_at"),
    )
    record = IngestionRecord(
        id=new_record_id(""),
        provider=provider,
        external_id=payload["external_id"],
        entity_type="REFUND",
        raw_payload=raw,
        fingerprint=row_fingerprint,
        status="PROCESSED",
        run_id=run_id,
    )
    db.add_all([refund, record])
    return refund, record


async def _materialize_fee(
    db: AsyncSession, run_id: str, payload: dict, raw: dict, row_fingerprint: str
) -> tuple[Fee, IngestionRecord]:
    provider = payload["provider"]
    merchant = await _resolve_by_ref(db, Merchant, payload["merchant_ref"])
    _require("FEE", "merchant", merchant)

    payment = None
    if payload.get("payment_ref") is not None:
        payment = await _resolve_by_ref(
            db, Payment, payload["payment_ref"], provider_column=Payment.provider,
            provider_value=provider,
        )
        _require("FEE", "payment", payment)
    settlement = None
    if payload.get("settlement_ref") is not None:
        settlement = await _resolve_by_ref(
            db, Settlement, payload["settlement_ref"],
            provider_column=Settlement.provider, provider_value=provider,
        )
        _require("FEE", "settlement", settlement)
    if payment is not None and settlement is not None:
        raise MaterializationError(
            DOMAIN_RULE_VIOLATION,
            "FEE cannot reference both a payment and a settlement",
        )

    fee = Fee(
        id=new_record_id("FEE"),
        external_id=payload["external_id"],
        merchant_id=merchant.id,
        payment_id=payment.id if payment else None,
        settlement_id=settlement.id if settlement else None,
        fee_type=payload["fee_type"],
        amount=payload["amount"],
        currency=payload["currency"],
        provider=provider,
    )
    record = IngestionRecord(
        id=new_record_id(""),
        provider=provider,
        external_id=payload["external_id"],
        entity_type="FEE",
        raw_payload=raw,
        fingerprint=row_fingerprint,
        status="PROCESSED",
        run_id=run_id,
    )
    db.add_all([fee, record])
    return fee, record


async def _materialize_settlement(
    db: AsyncSession, run_id: str, payload: dict, raw: dict, row_fingerprint: str
) -> tuple[Settlement, IngestionRecord]:
    provider = payload["provider"]
    merchant = await _resolve_by_ref(db, Merchant, payload["merchant_ref"])
    _require("SETTLEMENT", "merchant", merchant)

    gross = payload["gross_amount"]
    fee = payload["fee_amount"]
    adjustment = payload["adjustment_amount"]
    expected_net = payload.get("expected_net_amount")
    if expected_net is None:
        expected_net = gross - fee + adjustment
    else:
        # M2 domain rule: gross - fee + adjustment must equal expected net.
        try:
            validate_settlement_totals(gross, fee, adjustment, expected_net)
        except ValueError as exc:
            raise MaterializationError(DOMAIN_RULE_VIOLATION, str(exc))

    settlement = Settlement(
        id=new_record_id("SETTLEMENT"),
        external_id=payload["external_id"],
        merchant_id=merchant.id,
        provider=provider,
        gross_amount=gross,
        fee_amount=fee,
        adjustment_amount=adjustment,
        expected_net_amount=expected_net,
        actual_settled_amount=payload.get("actual_settled_amount"),
        currency=payload["currency"],
        settlement_date=payload["settlement_date"],
        status=payload["status"],
    )
    record = IngestionRecord(
        id=new_record_id(""),
        provider=provider,
        external_id=payload["external_id"],
        entity_type="SETTLEMENT",
        raw_payload=raw,
        fingerprint=row_fingerprint,
        status="PROCESSED",
        run_id=run_id,
    )
    db.add_all([settlement, record])
    return settlement, record


async def _materialize_bank_transaction(
    db: AsyncSession, run_id: str, payload: dict, raw: dict, row_fingerprint: str
) -> tuple[BankTransaction, IngestionRecord]:
    provider = payload["provider"]
    merchant = await _resolve_by_ref(db, Merchant, payload["merchant_ref"])
    _require("BANK_TRANSACTION", "merchant", merchant)

    settlement = None
    if payload.get("settlement_ref") is not None:
        # A bank feed references a settlement by external id WITHOUT provider
        # scoping: the settlement's provider is the gateway that produced the
        # payout, which differs from the bank provider ingesting the feed.
        settlement = await _resolve_by_ref(db, Settlement, payload["settlement_ref"])
        _require("BANK_TRANSACTION", "settlement", settlement)

    bank = BankTransaction(
        id=new_record_id("BANK_TRANSACTION"),
        external_id=payload["external_id"],
        merchant_id=merchant.id,
        bank_provider=provider,
        settlement_id=settlement.id if settlement else None,
        amount=payload["amount"],
        currency=payload["currency"],
        transaction_type=payload["transaction_type"],
        transaction_date=payload["transaction_date"],
        description=payload.get("description"),
        status=payload["status"],
    )
    record = IngestionRecord(
        id=new_record_id(""),
        provider=provider,
        external_id=payload["external_id"],
        entity_type="BANK_TRANSACTION",
        raw_payload=raw,
        fingerprint=row_fingerprint,
        status="PROCESSED",
        run_id=run_id,
    )
    db.add_all([bank, record])
    return bank, record


_MATERIALIZERS = {
    "PAYMENT": _materialize_payment,
    "REFUND": _materialize_refund,
    "FEE": _materialize_fee,
    "SETTLEMENT": _materialize_settlement,
    "BANK_TRANSACTION": _materialize_bank_transaction,
}


async def materialize_domain_fact(
    db: AsyncSession,
    run_id: str,
    entity_type: str,
    payload: dict,
    raw: dict,
    row_fingerprint: str,
):
    """Persist one ACCEPTED normalized row into the financial domain.

    Raises MaterializationError for reference/domain failures (row is
    REJECTED). IntegrityError bubbles to the caller for DUPLICATE handling.
    """
    materializer = _MATERIALIZERS.get(entity_type)
    if materializer is None:
        raise MaterializationError(
            DOMAIN_RULE_VIOLATION, f"no materializer for entity type {entity_type}"
        )
    return await materializer(db, run_id, payload, raw, row_fingerprint)
