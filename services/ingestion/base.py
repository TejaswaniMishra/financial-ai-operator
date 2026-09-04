import hashlib
import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from decimal import Decimal

from database.models.ingestion import IngestionRecord, IngestionException


def generate_fingerprint(payload: dict) -> str:
    """
    Generates a deterministic SHA-256 fingerprint for a JSON-serializable payload.
    """
    # Sort keys to ensure deterministic serialization
    serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


# ─── Deterministic domain validation rules (M2) ─────────────────────────────
# These module functions are the single source of truth for the financial
# domain rules. The IngestionService methods below delegate to them so the
# original M2 API and the M13 batch pipeline share identical semantics.


def validate_refund_domain_rules(
    refund_amount: Decimal,
    payment_amount: Decimal,
    refund_currency: str,
    payment_currency: str,
) -> None:
    """A refund can never exceed its parent payment or change currency."""
    if refund_amount > payment_amount:
        raise ValueError(f"Refund amount {refund_amount} exceeds payment amount {payment_amount}")
    if refund_currency != payment_currency:
        raise ValueError(f"Refund currency {refund_currency} does not match payment currency {payment_currency}")


def validate_settlement_totals(
    gross: Decimal,
    fee: Decimal,
    adjustment: Decimal,
    expected_net: Decimal,
) -> None:
    """gross - fee + adjustment must equal the expected net amount."""
    calculated_net = gross - fee + adjustment
    if expected_net != calculated_net:
        raise ValueError(
            f"Settlement totals invalid: {gross} - {fee} + {adjustment} != {expected_net}"
        )


class IngestionService:
    """
    Base service for deterministic ingestion of financial records.
    Provides methods to check for idempotency, record ingestion exceptions,
    and manage ingestion records.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_existing_record_by_fingerprint(self, fingerprint: str) -> Optional[IngestionRecord]:
        stmt = select(IngestionRecord).where(IngestionRecord.fingerprint == fingerprint)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_existing_record_by_provider_ext_id(
        self, provider: str, external_id: str, entity_type: str
    ) -> Optional[IngestionRecord]:
        stmt = select(IngestionRecord).where(
            IngestionRecord.provider == provider,
            IngestionRecord.external_id == external_id,
            IngestionRecord.entity_type == entity_type
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_ingestion_record(
        self,
        record_id: str,
        provider: str,
        external_id: str,
        entity_type: str,
        raw_payload: dict,
        status: str = "PROCESSED"
    ) -> IngestionRecord:
        fingerprint = generate_fingerprint(raw_payload)
        record = IngestionRecord(
            id=record_id,
            provider=provider,
            external_id=external_id,
            entity_type=entity_type,
            raw_payload=raw_payload,
            fingerprint=fingerprint,
            status=status
        )
        self.session.add(record)
        return record

    async def validate_refund_domain_rules(self, refund_amount: Decimal, payment_amount: Decimal, refund_currency: str, payment_currency: str):
        return validate_refund_domain_rules(
            refund_amount, payment_amount, refund_currency, payment_currency
        )

    async def validate_settlement_totals(self, gross: Decimal, fee: Decimal, adj: Decimal, expected_net: Decimal):
        return validate_settlement_totals(gross, fee, adj, expected_net)

    async def create_ingestion_exception(
        self, exception_id: str, ingestion_record_id: str, error_message: str
    ) -> IngestionException:
        exception = IngestionException(
            id=exception_id,
            ingestion_record_id=ingestion_record_id,
            error_message=error_message
        )
        self.session.add(exception)
        
        # Mark the ingestion record as an EXCEPTION
        stmt = select(IngestionRecord).where(IngestionRecord.id == ingestion_record_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            record.status = "EXCEPTION"
            
        return exception
