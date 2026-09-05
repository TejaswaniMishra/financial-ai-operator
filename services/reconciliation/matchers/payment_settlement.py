from datetime import timedelta, datetime, timezone
import uuid
from decimal import Decimal
from sqlalchemy import select, and_, not_
from sqlalchemy.orm import selectinload

from database.models import Payment, Settlement, SettlementItem, Fee
from database.models.reconciliation import (
    ReconciliationRelationship, Discrepancy, 
    RelationshipStatus, FinancialEvaluationStatus, DiscrepancyType, Severity
)
from packages.schemas.reconciliation import (
    RelationshipStatus as RelStatusEnum,
    FinancialEvaluationStatus as FinStatusEnum,
    DiscrepancyType as DiscTypeEnum,
    Severity as SevEnum
)
from services.reconciliation.matchers.base import BaseMatcher

class PaymentToSettlementMatcher(BaseMatcher):
    
    async def run(self) -> dict[str, int]:
        stats = {"processed": 0, "relationships_created": 0, "discrepancies": 0}
        
        # Candidate window: 14 days ago to now
        window_start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14)
        
        # We find payments in this window
        stmt = select(Payment).options(
            selectinload(Payment.fees),
            selectinload(Payment.settlement_items)
        ).where(Payment.processed_at >= window_start)
        
        result = await self.session.execute(stmt)
        payments = result.scalars().all()
        
        for payment in payments:
            stats["processed"] += 1
            
            # Find settlement items for this payment
            items = payment.settlement_items
            if not items:
                # UNRESOLVED relationship. We can optionally flag if it's too old (MISSING_SETTLEMENT)
                # Let's check if it's older than 3 days
                if datetime.now(timezone.utc).replace(tzinfo=None) - payment.processed_at > timedelta(days=3):
                    created_disc = await self._create_missing_settlement_discrepancy(payment)
                    if created_disc:
                        stats["discrepancies"] += 1
                continue
            
            # The explicit lineage gives us CONFIRMED relationships
            for item in items:
                rel_status = RelStatusEnum.CONFIRMED
                fin_status = FinStatusEnum.RECONCILED
                
                # Check financial evidence
                # E.g., does the settlement item amount match the payment amount?
                evidence = {
                    "strategy": "PaymentToSettlementMatcher",
                    "payment_amount": str(payment.amount),
                    "item_amount": str(item.amount),
                    "currency_match": payment.currency == item.currency
                }
                
                discrepancy_data = None
                
                # 1. Amount mismatch
                if payment.amount != item.amount:
                    fin_status = FinStatusEnum.DISCREPANCY
                    discrepancy_data = {
                        "rule_code": "PAYMENT_SETTLEMENT_AMOUNT_001",
                        "disc_type": DiscTypeEnum.AMOUNT_MISMATCH,
                        "payment": payment,
                        "target_id": item.id,
                        "target_type": "SETTLEMENT_ITEM",
                        "expected": payment.amount,
                        "actual": item.amount
                    }
                    
                # 2. Currency mismatch
                elif payment.currency != item.currency:
                    fin_status = FinStatusEnum.DISCREPANCY
                    discrepancy_data = {
                        "rule_code": "PAYMENT_SETTLEMENT_CURRENCY_001",
                        "disc_type": DiscTypeEnum.CURRENCY_MISMATCH,
                        "payment": payment,
                        "target_id": item.id,
                        "target_type": "SETTLEMENT_ITEM",
                        "expected": None,
                        "actual": None
                    }
                
                # Create Relationship
                created = await self._upsert_relationship(
                    source_id=payment.id,
                    source_type="PAYMENT",
                    target_id=item.settlement_id,
                    target_type="SETTLEMENT",
                    rel_type="PAYMENT_TO_SETTLEMENT",
                    rel_status=rel_status,
                    fin_status=fin_status,
                    evidence=evidence
                )
                if created:
                    stats["relationships_created"] += 1
                
                if discrepancy_data:
                    created_disc = await self._upsert_discrepancy(**discrepancy_data)
                    if created_disc:
                        stats["discrepancies"] += 1

        return stats

    async def _upsert_relationship(self, source_id, source_type, target_id, target_type, rel_type, rel_status, fin_status, evidence):
        # We need a deterministic ID or check for existence to ensure idempotency across runs
        # We use a simple select to check if equivalent exists for simplicity in SQLite, 
        # though ON CONFLICT is better for Postgres.
        stmt = select(ReconciliationRelationship).where(
            and_(
                ReconciliationRelationship.source_entity_id == source_id,
                ReconciliationRelationship.target_entity_id == target_id,
                ReconciliationRelationship.relationship_type == rel_type
            )
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if not existing:
            rel = ReconciliationRelationship(
                id=str(uuid.uuid4()),
                run_id=self.run_id,
                source_entity_type=source_type,
                source_entity_id=source_id,
                target_entity_type=target_type,
                target_entity_id=target_id,
                relationship_type=rel_type,
                relationship_status=rel_status,
                financial_status=fin_status,
                evidence=evidence
            )
            self.session.add(rel)
            await self.session.flush()  # make insert visible within this transaction before the next SELECT
            return True
        return False

    async def _upsert_discrepancy(self, rule_code, disc_type, payment, target_id, target_type, expected, actual):
        stmt = select(Discrepancy).where(
            and_(
                Discrepancy.source_entity_id == payment.id,
                Discrepancy.rule_code == rule_code
            )
        )
        result = await self.session.execute(stmt)
        if not result.scalar_one_or_none():
            disc = Discrepancy(
                id=str(uuid.uuid4()),
                run_id=self.run_id,
                rule_code=rule_code,
                discrepancy_type=disc_type,
                severity=SevEnum.HIGH,
                source_entity_type="PAYMENT",
                source_entity_id=payment.id,
                related_entity_type=target_type,
                related_entity_id=target_id,
                expected_amount=expected,
                actual_amount=actual,
                difference_amount=abs(expected - actual) if expected is not None and actual is not None else None,
                currency=payment.currency
            )
            self.session.add(disc)
            await self.session.flush()  # make insert visible within this transaction before the next SELECT
            return True
        return False
        
    async def _create_missing_settlement_discrepancy(self, payment):
        # Check if already exists to avoid dupes across runs
        stmt = select(Discrepancy).where(
            and_(
                Discrepancy.source_entity_id == payment.id,
                Discrepancy.rule_code == "PAYMENT_MISSING_SETTLEMENT_001"
            )
        )
        result = await self.session.execute(stmt)
        if not result.scalar_one_or_none():
            disc = Discrepancy(
                id=str(uuid.uuid4()),
                run_id=self.run_id,
                rule_code="PAYMENT_MISSING_SETTLEMENT_001",
                discrepancy_type=DiscTypeEnum.MISSING_SETTLEMENT,
                severity=SevEnum.HIGH,
                source_entity_type="PAYMENT",
                source_entity_id=payment.id,
                currency=payment.currency,
                expected_amount=payment.amount
            )
            self.session.add(disc)
            return True
        return False
