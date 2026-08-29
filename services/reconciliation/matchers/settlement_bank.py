from datetime import timedelta, datetime, timezone
import uuid
from decimal import Decimal
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from database.models import Settlement, BankTransaction
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

class SettlementToBankTransactionMatcher(BaseMatcher):
    
    async def run(self) -> dict[str, int]:
        stats = {"processed": 0, "relationships_created": 0, "discrepancies": 0}
        
        # Candidate window: 14 days ago to now
        window_start = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14)
        
        stmt = select(Settlement).options(
            selectinload(Settlement.bank_transactions)
        ).where(Settlement.settlement_date >= window_start)
        
        result = await self.session.execute(stmt)
        settlements = result.scalars().all()
        
        for settlement in settlements:
            stats["processed"] += 1
            
            # Check internal arithmetic (Fee discrepancy)
            # expected_net = gross - fee + adj
            # if expected != actual, record FEE discrepancy
            expected_net = (settlement.gross_amount or Decimal(0)) - (settlement.fee_amount or Decimal(0)) + (settlement.adjustment_amount or Decimal(0))
            
            if settlement.actual_settled_amount and expected_net != settlement.actual_settled_amount:
                # Fee discrepancy
                created = await self._upsert_discrepancy(
                    rule_code="SETTLEMENT_FEE_MISMATCH_001",
                    disc_type=DiscTypeEnum.FEE_MISMATCH,
                    sev=SevEnum.MEDIUM,
                    source_id=settlement.id,
                    target_id=None,
                    expected=expected_net,
                    actual=settlement.actual_settled_amount,
                    currency=settlement.currency
                )
                if created:
                    stats["discrepancies"] += 1

            bank_txs = settlement.bank_transactions
            if not bank_txs:
                # Missing bank tx if it's older than 3 days
                if datetime.now(timezone.utc).replace(tzinfo=None) - settlement.settlement_date > timedelta(days=3):
                    created = await self._upsert_discrepancy(
                        rule_code="SETTLEMENT_MISSING_BANK_TX_001",
                        disc_type=DiscTypeEnum.MISSING_BANK_TX,
                        sev=SevEnum.HIGH,
                        source_id=settlement.id,
                        target_id=None,
                        expected=settlement.actual_settled_amount or expected_net,
                        actual=None,
                        currency=settlement.currency
                    )
                    if created:
                        stats["discrepancies"] += 1
                continue
            
            for btx in bank_txs:
                rel_status = RelStatusEnum.CONFIRMED
                fin_status = FinStatusEnum.RECONCILED
                
                evidence = {
                    "strategy": "SettlementToBankTransactionMatcher",
                    "settlement_expected": str(expected_net),
                    "settlement_actual": str(settlement.actual_settled_amount) if settlement.actual_settled_amount else None,
                    "bank_amount": str(btx.amount),
                    "currency_match": settlement.currency == btx.currency,
                    "date_diff_days": (btx.transaction_date - settlement.settlement_date).days if btx.transaction_date and settlement.settlement_date else None
                }
                
                # Financial Evaluations
                
                # 1. Amount mismatch (Bank amount vs Actual settled)
                amount_to_match = settlement.actual_settled_amount if settlement.actual_settled_amount else expected_net
                if btx.amount != amount_to_match:
                    fin_status = FinStatusEnum.DISCREPANCY
                    created = await self._upsert_discrepancy(
                        rule_code="SETTLEMENT_BANK_AMOUNT_001",
                        disc_type=DiscTypeEnum.AMOUNT_MISMATCH,
                        sev=SevEnum.HIGH,
                        source_id=settlement.id,
                        target_id=btx.id,
                        expected=amount_to_match,
                        actual=btx.amount,
                        currency=settlement.currency
                    )
                    if created:
                        stats["discrepancies"] += 1
                    
                # 2. Timing policy: bank tx arrived > 3 days late
                elif evidence["date_diff_days"] is not None and evidence["date_diff_days"] > 3:
                    fin_status = FinStatusEnum.DISCREPANCY
                    created = await self._upsert_discrepancy(
                        rule_code="SETTLEMENT_TIMING_001",
                        disc_type=DiscTypeEnum.LATE_ARRIVAL,
                        sev=SevEnum.LOW,
                        source_id=settlement.id,
                        target_id=btx.id,
                        expected=None,
                        actual=None,
                        currency=settlement.currency
                    )
                    if created:
                        stats["discrepancies"] += 1
                    
                # 3. Currency mismatch
                elif settlement.currency != btx.currency:
                    fin_status = FinStatusEnum.DISCREPANCY
                    created = await self._upsert_discrepancy(
                        rule_code="SETTLEMENT_BANK_CURRENCY_001",
                        disc_type=DiscTypeEnum.CURRENCY_MISMATCH,
                        sev=SevEnum.HIGH,
                        source_id=settlement.id,
                        target_id=btx.id,
                        expected=None,
                        actual=None,
                        currency=settlement.currency
                    )
                    if created:
                        stats["discrepancies"] += 1

                # Create Relationship
                created = await self._upsert_relationship(
                    source_id=settlement.id,
                    source_type="SETTLEMENT",
                    target_id=btx.id,
                    target_type="BANK_TRANSACTION",
                    rel_type="SETTLEMENT_TO_BANK",
                    rel_status=rel_status,
                    fin_status=fin_status,
                    evidence=evidence
                )
                if created:
                    stats["relationships_created"] += 1

        return stats

    async def _upsert_relationship(self, source_id, source_type, target_id, target_type, rel_type, rel_status, fin_status, evidence):
        stmt = select(ReconciliationRelationship).where(
            and_(
                ReconciliationRelationship.source_entity_id == source_id,
                ReconciliationRelationship.target_entity_id == target_id,
                ReconciliationRelationship.relationship_type == rel_type
            )
        )
        result = await self.session.execute(stmt)
        if not result.scalar_one_or_none():
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
            return True
        return False

    async def _upsert_discrepancy(self, rule_code, disc_type, sev, source_id, target_id, expected, actual, currency):
        stmt = select(Discrepancy).where(
            and_(
                Discrepancy.source_entity_id == source_id,
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
                severity=sev,
                source_entity_type="SETTLEMENT",
                source_entity_id=source_id,
                related_entity_type="BANK_TRANSACTION" if target_id else None,
                related_entity_id=target_id,
                expected_amount=expected,
                actual_amount=actual,
                difference_amount=abs(expected - actual) if expected is not None and actual is not None else None,
                currency=currency
            )
            self.session.add(disc)
            return True
        return False
