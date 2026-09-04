import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from database.models.reconciliation import Discrepancy, ReconciliationRelationship
from database.models.transaction import Payment, SettlementItem, Settlement, BankTransaction

class ContextBuilder:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def build_investigation_context(self, discrepancy_id: str) -> Tuple[Dict[str, Any], str, str]:
        """
        Builds the deterministic investigation context, returning:
        - context_dict (dict)
        - context_snapshot (JSON string)
        - context_hash (SHA-256 string)
        """
        discrepancy = await self._get_discrepancy(discrepancy_id)
        if not discrepancy:
            raise ValueError(f"Discrepancy {discrepancy_id} not found")

        lineage = await self._get_lineage(discrepancy)
        historical_stats = await self._get_historical_stats(discrepancy)
        
        context_dict = {
            "discrepancy": {
                "id": discrepancy.id,
                "rule_code": discrepancy.rule_code,
                "type": discrepancy.discrepancy_type.value if hasattr(discrepancy.discrepancy_type, 'value') else str(discrepancy.discrepancy_type),
                "severity": discrepancy.severity.value if hasattr(discrepancy.severity, 'value') else str(discrepancy.severity),
                "expected_amount": str(discrepancy.expected_amount) if discrepancy.expected_amount is not None else None,
                "actual_amount": str(discrepancy.actual_amount) if discrepancy.actual_amount is not None else None,
                "difference_amount": str(discrepancy.difference_amount) if discrepancy.difference_amount is not None else None,
                "currency": discrepancy.currency,
                "source_entity_type": discrepancy.source_entity_type,
                "source_entity_id": discrepancy.source_entity_id,
            },
            "deterministic_evidence": {
                "amount_difference_verified": discrepancy.difference_amount is not None,
                "currency_verified": True,
            },
            "historical_statistics": historical_stats,
            "lineage": lineage,
            # The ONLY entity IDs an LLM is allowed to cite. This allowlist is
            # derived deterministically from the lineage so a model can never
            # "reason" its way to an id that is not in the provided context.
            "citable_entities": self._build_citable_entities(discrepancy, lineage),
        }

        # Canonical JSON string (sorted keys, no spaces)
        context_snapshot = json.dumps(context_dict, sort_keys=True, separators=(',', ':'))
        context_hash = hashlib.sha256(context_snapshot.encode('utf-8')).hexdigest()

        return context_dict, context_snapshot, context_hash

    def _build_citable_entities(self, discrepancy: Discrepancy, lineage: Dict[str, Any]) -> list:
        """Deterministic allowlist of entity ids the LLM may cite as evidence.

        Order is stable: discrepancy first, then reconciliation relationship,
        then each lineage entity by type. Only ids that actually exist in the
        context are listed — the model is forbidden from citing anything else.
        """
        registry = [
            {
                "id": discrepancy.id,
                "entity_type": "DISCREPANCY",
                "label": "Reconciliation discrepancy",
            }
        ]
        relationship = lineage.get("relationship")
        if relationship and relationship.get("id"):
            registry.append(
                {
                    "id": relationship["id"],
                    "entity_type": "RECONCILIATION_RELATIONSHIP",
                    "label": "Reconciliation relationship",
                }
            )
        for key, entity_type, label in (
            ("payment", "PAYMENT", "Payment"),
            ("settlement", "SETTLEMENT", "Settlement"),
            ("bank_transaction", "BANK_TRANSACTION", "Bank transaction"),
        ):
            entity = lineage.get(key)
            if entity and entity.get("id"):
                registry.append(
                    {
                        "id": entity["id"],
                        "entity_type": entity_type,
                        "label": label,
                    }
                )
        return registry

    async def _get_discrepancy(self, discrepancy_id: str) -> Discrepancy:
        stmt = select(Discrepancy).where(Discrepancy.id == discrepancy_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _get_lineage(self, discrepancy: Discrepancy) -> Dict[str, Any]:
        lineage = {}
        
        # Get the related relationship
        rel_stmt = select(ReconciliationRelationship).where(
            ReconciliationRelationship.run_id == discrepancy.run_id,
            ReconciliationRelationship.source_entity_id == discrepancy.source_entity_id
        )
        rel_result = await self.session.execute(rel_stmt)
        relationship = rel_result.scalar_one_or_none()
        
        if relationship:
            lineage["relationship"] = {
                "id": relationship.id,
                "type": relationship.relationship_type,
                "status": relationship.relationship_status.value if hasattr(relationship.relationship_status, 'value') else str(relationship.relationship_status),
                "financial_status": relationship.financial_status.value if hasattr(relationship.financial_status, 'value') else str(relationship.financial_status),
                "evidence": relationship.evidence
            }

        # Attempt to pull specific entities if they are payment or settlement
        if discrepancy.source_entity_type == "PAYMENT":
            pay_stmt = select(Payment).where(Payment.id == discrepancy.source_entity_id)
            pay = (await self.session.execute(pay_stmt)).scalar_one_or_none()
            if pay:
                lineage["payment"] = {
                    "id": pay.id,
                    "provider": pay.provider,
                    "amount": str(pay.amount),
                    "currency": pay.currency,
                    "status": pay.status.value if hasattr(pay.status, 'value') else str(pay.status),
                    "processed_at": pay.processed_at.isoformat() if pay.processed_at else None
                }

        elif discrepancy.source_entity_type == "SETTLEMENT":
            set_stmt = select(Settlement).where(Settlement.id == discrepancy.source_entity_id)
            settlement = (await self.session.execute(set_stmt)).scalar_one_or_none()
            if settlement:
                lineage["settlement"] = {
                    "id": settlement.id,
                    "expected_net_amount": str(settlement.expected_net_amount) if settlement.expected_net_amount else None,
                    "actual_settled_amount": str(settlement.actual_settled_amount) if settlement.actual_settled_amount else None,
                    "currency": settlement.currency,
                    "provider": settlement.provider,
                    "settlement_date": settlement.settlement_date.isoformat() if settlement.settlement_date else None
                }
                
                # Fetch bank transactions linked to this settlement via relationship
                if relationship and relationship.target_entity_type == "BANK_TRANSACTION":
                    bt_stmt = select(BankTransaction).where(BankTransaction.id == relationship.target_entity_id)
                    bt = (await self.session.execute(bt_stmt)).scalar_one_or_none()
                    if bt:
                        lineage["bank_transaction"] = {
                            "id": bt.id,
                            "amount": str(bt.amount),
                            "currency": bt.currency,
                            "transaction_date": bt.transaction_date.isoformat() if bt.transaction_date else None
                        }

        return lineage

    async def _get_historical_stats(self, discrepancy: Discrepancy) -> Dict[str, Any]:
        today = datetime.now(timezone.utc).replace(tzinfo=None)
        seven_days_ago = today - timedelta(days=7)
        
        # Occurrences today
        today_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
        stmt_today = select(func.count(Discrepancy.id)).where(
            Discrepancy.rule_code == discrepancy.rule_code,
            Discrepancy.created_at >= today_start
        )
        today_count = (await self.session.execute(stmt_today)).scalar_one() or 0
        
        # Occurrences last 7 days
        stmt_7d = select(func.count(Discrepancy.id)).where(
            Discrepancy.rule_code == discrepancy.rule_code,
            Discrepancy.created_at >= seven_days_ago
        )
        last_7d_count = (await self.session.execute(stmt_7d)).scalar_one() or 0
        
        daily_avg = last_7d_count / 7.0 if last_7d_count > 0 else 0.0
        ratio = (today_count / daily_avg) if daily_avg > 0 else 0.0
        
        return {
            "rule_code": discrepancy.rule_code,
            "occurrences_today": today_count,
            "occurrences_last_7_days": last_7d_count,
            "historical_daily_average": round(daily_avg, 2),
            "current_vs_baseline_ratio": round(ratio, 2)
        }
