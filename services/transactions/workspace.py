"""M9 — Transaction workspace read service.

A safe, read-only unification layer over the authoritative financial tables
(Payment, Refund, Fee, Settlement, BankTransaction). The database remains the
source of truth; this module never mutates financial facts.

The list query paginates a deterministic SQL UNION of the five record types
(created_at DESC, id DESC), then decorates the page with merchant names and
derived reconciliation/discrepancy state via a small number of indexed
IN-queries (no N+1).
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    and_,
    cast,
    desc,
    exists,
    func,
    literal,
    or_,
    select,
    union_all,
    Numeric,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.merchant import Merchant
from database.models.transaction import (
    BankTransaction,
    Fee,
    Order,
    Payment,
    Refund,
    Settlement,
    SettlementItem,
)
from database.models.reconciliation import (
    Discrepancy,
    ReconciliationRelationship,
    ReconciliationRun,
)
from database.models.investigation import Investigation
from database.models.action_request import ActionRequest
from database.models.action_execution import ActionExecution

PAYMENT = "PAYMENT"
REFUND = "REFUND"
FEE = "FEE"
SETTLEMENT = "SETTLEMENT"
BANK_TRANSACTION = "BANK_TRANSACTION"

ALL_TYPES = (PAYMENT, REFUND, FEE, SETTLEMENT, BANK_TRANSACTION)

DEFAULT_LIMIT = 50
MAX_LIMIT = 200

# ─── Filter model ────────────────────────────────────────────────────────────


class WorkspaceFilters:
    """Validated, shared filter set for the transaction list query."""

    def __init__(
        self,
        record_type: Optional[str] = None,
        status: Optional[str] = None,
        currency: Optional[str] = None,
        merchant_id: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        min_amount: Optional[Decimal] = None,
        max_amount: Optional[Decimal] = None,
        reconciled: Optional[bool] = None,
        has_discrepancy: Optional[bool] = None,
        search: Optional[str] = None,
    ):
        self.record_type = record_type
        self.status = status
        self.currency = currency
        self.merchant_id = merchant_id
        self.date_from = date_from
        self.date_to = date_to
        self.min_amount = min_amount
        self.max_amount = max_amount
        self.reconciled = reconciled
        self.has_discrepancy = has_discrepancy
        self.search = (search or "").strip() or None


def _amount_predicates(min_amount, max_amount, column):
    preds = []
    if min_amount is not None:
        preds.append(column >= min_amount)
    if max_amount is not None:
        preds.append(column <= max_amount)
    return preds


def _date_predicates(f: WorkspaceFilters, column):
    preds = []
    if f.date_from is not None:
        preds.append(column >= f.date_from)
    if f.date_to is not None:
        preds.append(column <= f.date_to)
    return preds


async def _resolve_merchant_ids(db: AsyncSession, search: str) -> list[str]:
    """Merchant-name search support: resolve matching merchant ids."""
    stmt = select(Merchant.id).where(Merchant.name.ilike(f"%{search}%"))
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


def _common_predicates(f: WorkspaceFilters, table, merchant_ids: Optional[list[str]]):
    """Shared predicates for tables that carry the standard columns."""
    preds = []
    if f.currency:
        preds.append(table.currency == f.currency)
    if f.merchant_id:
        preds.append(table.merchant_id == f.merchant_id)
    preds.extend(_date_predicates(f, table.created_at))
    preds.extend(_amount_predicates(f.min_amount, f.max_amount, _AMOUNT_FOR[table]))
    if f.search:
        # Search is a single OR group: id / external id / merchant name.
        like = f"%{f.search}%"
        group = [table.id.ilike(like), table.external_id.ilike(like)]
        if merchant_ids:
            group.append(table.merchant_id.in_(merchant_ids))
        preds.append(or_(*group))
    return preds


def _table_query(f: WorkspaceFilters, table, merchant_ids: Optional[list[str]], include_status: bool):
    """Build the filtered select for one table with the union column shape."""
    preds = _common_predicates(f, table, merchant_ids)
    if include_status and f.status:
        preds.append(table.status == f.status)
    if not include_status and f.status:
        # Fees have no status column; a status filter excludes them entirely.
        return None
    if f.reconciled is True:
        preds.append(
            exists().where(
                or_(
                    and_(
                        ReconciliationRelationship.source_entity_type == _TYPE_FOR[table],
                        ReconciliationRelationship.source_entity_id == table.id,
                    ),
                    and_(
                        ReconciliationRelationship.target_entity_type == _TYPE_FOR[table],
                        ReconciliationRelationship.target_entity_id == table.id,
                    ),
                )
            )
        )
    elif f.reconciled is False:
        preds.append(
            ~exists().where(
                or_(
                    and_(
                        ReconciliationRelationship.source_entity_type == _TYPE_FOR[table],
                        ReconciliationRelationship.source_entity_id == table.id,
                    ),
                    and_(
                        ReconciliationRelationship.target_entity_type == _TYPE_FOR[table],
                        ReconciliationRelationship.target_entity_id == table.id,
                    ),
                )
            )
        )
    if f.has_discrepancy is True:
        preds.append(
            exists().where(
                or_(
                    and_(
                        Discrepancy.source_entity_type == _TYPE_FOR[table],
                        Discrepancy.source_entity_id == table.id,
                    ),
                    and_(
                        Discrepancy.related_entity_type == _TYPE_FOR[table],
                        Discrepancy.related_entity_id == table.id,
                    ),
                )
            )
        )
    elif f.has_discrepancy is False:
        preds.append(
            ~exists().where(
                or_(
                    and_(
                        Discrepancy.source_entity_type == _TYPE_FOR[table],
                        Discrepancy.source_entity_id == table.id,
                    ),
                    and_(
                        Discrepancy.related_entity_type == _TYPE_FOR[table],
                        Discrepancy.related_entity_id == table.id,
                    ),
                )
            )
        )
    return preds


_TYPE_FOR = {
    Payment: PAYMENT,
    Refund: REFUND,
    Fee: FEE,
    Settlement: SETTLEMENT,
    BankTransaction: BANK_TRANSACTION,
}

_STATUS_FOR = {
    Payment: Payment.status,
    Refund: Refund.status,
    Fee: None,  # fees carry fee_type, not a lifecycle status
    Settlement: Settlement.status,
    BankTransaction: BankTransaction.status,
}

# Amount column varies by table: settlements carry gross/net figures instead
# of a single `amount`.
_AMOUNT_FOR = {
    Payment: Payment.amount,
    Refund: Refund.amount,
    Fee: Fee.amount,
    Settlement: Settlement.expected_net_amount,
    BankTransaction: BankTransaction.amount,
}

_PROVIDER_FOR = {
    Payment: Payment.provider,
    Refund: Refund.provider,
    Fee: Fee.provider,
    Settlement: Settlement.provider,
    BankTransaction: BankTransaction.bank_provider,
}


def _count_query(table, record_type: str, f: WorkspaceFilters, merchant_ids, include_status: bool):
    preds = _common_predicates(f, table, merchant_ids)
    if include_status and f.status:
        preds.append(table.status == f.status)
    if not include_status and f.status:
        return None
    if f.reconciled is True:
        preds.append(
            exists().where(
                or_(
                    and_(
                        ReconciliationRelationship.source_entity_type == record_type,
                        ReconciliationRelationship.source_entity_id == table.id,
                    ),
                    and_(
                        ReconciliationRelationship.target_entity_type == record_type,
                        ReconciliationRelationship.target_entity_id == table.id,
                    ),
                )
            )
        )
    elif f.reconciled is False:
        preds.append(
            ~exists().where(
                or_(
                    and_(
                        ReconciliationRelationship.source_entity_type == record_type,
                        ReconciliationRelationship.source_entity_id == table.id,
                    ),
                    and_(
                        ReconciliationRelationship.target_entity_type == record_type,
                        ReconciliationRelationship.target_entity_id == table.id,
                    ),
                )
            )
        )
    if f.has_discrepancy is True:
        preds.append(
            exists().where(
                or_(
                    and_(
                        Discrepancy.source_entity_type == record_type,
                        Discrepancy.source_entity_id == table.id,
                    ),
                    and_(
                        Discrepancy.related_entity_type == record_type,
                        Discrepancy.related_entity_id == table.id,
                    ),
                )
            )
        )
    elif f.has_discrepancy is False:
        preds.append(
            ~exists().where(
                or_(
                    and_(
                        Discrepancy.source_entity_type == record_type,
                        Discrepancy.source_entity_id == table.id,
                    ),
                    and_(
                        Discrepancy.related_entity_type == record_type,
                        Discrepancy.related_entity_id == table.id,
                    ),
                )
            )
        )
    stmt = select(func.count()).select_from(table)
    if preds:
        stmt = stmt.where(*preds)
    return stmt


async def list_transactions(
    db: AsyncSession,
    *,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    record_type: Optional[str] = None,
    status: Optional[str] = None,
    currency: Optional[str] = None,
    merchant_id: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    min_amount: Optional[Decimal] = None,
    max_amount: Optional[Decimal] = None,
    reconciled: Optional[bool] = None,
    has_discrepancy: Optional[bool] = None,
    search: Optional[str] = None,
) -> dict[str, Any]:
    """Paginated, filtered, deterministic read of the unified workspace."""
    f = WorkspaceFilters(
        record_type=record_type,
        status=status,
        currency=currency,
        merchant_id=merchant_id,
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        reconciled=reconciled,
        has_discrepancy=has_discrepancy,
        search=search,
    )

    merchant_ids = None
    if f.search:
        merchant_ids = await _resolve_merchant_ids(db, f.search)

    tables = (
        (Payment, PAYMENT, True),
        (Refund, REFUND, True),
        (Fee, FEE, False),
        (Settlement, SETTLEMENT, True),
        (BankTransaction, BANK_TRANSACTION, True),
    )

    # ── Counts (summary + total) — counts reflect the exact filter set in
    #    effect, so the UI KPI cards always show real backend numbers. ──────
    summary: dict[str, int] = {t: 0 for t in ALL_TYPES}
    total = 0
    for table, rtype, has_status in tables:
        if f.record_type and rtype != f.record_type:
            continue
        stmt = _count_query(table, rtype, f, merchant_ids, has_status)
        if stmt is None:
            continue
        count = (await db.execute(stmt)).scalar_one()
        summary[rtype] = count
        total += count
    summary["total"] = total

    # ── Page via deterministic union ───────────────────────────────────────
    union_parts = []
    for table, rtype, has_status in tables:
        if f.record_type and rtype != f.record_type:
            continue
        status_col = _STATUS_FOR[table]
        preds = _common_predicates(f, table, merchant_ids)
        if has_status and f.status:
            preds.append(table.status == f.status)
        if not has_status and f.status:
            continue
        if f.reconciled is True:
            preds.append(
                exists().where(
                    or_(
                        and_(ReconciliationRelationship.source_entity_type == rtype, ReconciliationRelationship.source_entity_id == table.id),
                        and_(ReconciliationRelationship.target_entity_type == rtype, ReconciliationRelationship.target_entity_id == table.id),
                    )
                )
            )
        elif f.reconciled is False:
            preds.append(
                ~exists().where(
                    or_(
                        and_(ReconciliationRelationship.source_entity_type == rtype, ReconciliationRelationship.source_entity_id == table.id),
                        and_(ReconciliationRelationship.target_entity_type == rtype, ReconciliationRelationship.target_entity_id == table.id),
                    )
                )
            )
        if f.has_discrepancy is True:
            preds.append(
                exists().where(
                    or_(
                        and_(Discrepancy.source_entity_type == rtype, Discrepancy.source_entity_id == table.id),
                        and_(Discrepancy.related_entity_type == rtype, Discrepancy.related_entity_id == table.id),
                    )
                )
            )
        elif f.has_discrepancy is False:
            preds.append(
                ~exists().where(
                    or_(
                        and_(Discrepancy.source_entity_type == rtype, Discrepancy.source_entity_id == table.id),
                        and_(Discrepancy.related_entity_type == rtype, Discrepancy.related_entity_id == table.id),
                    )
                )
            )
        sel = select(
            table.id.label("id"),
            literal(rtype).label("record_type"),
            table.external_id.label("external_id"),
            table.merchant_id.label("merchant_id"),
            _PROVIDER_FOR[table].label("provider"),
            cast(_AMOUNT_FOR[table], Numeric(20, 4)).label("amount"),
            table.currency.label("currency"),
            (status_col.label("status") if status_col is not None else literal("N/A").label("status")),
            table.created_at.label("created_at"),
        )
        if preds:
            sel = sel.where(*preds)
        union_parts.append(sel)

    items: list[dict[str, Any]] = []
    if union_parts:
        union = union_all(*union_parts).subquery()
        stmt = (
            select(union)
            .order_by(desc(union.c.created_at), desc(union.c.id))
            .offset(offset)
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        items = [
            {
                "id": r.id,
                "record_type": r.record_type,
                "external_id": r.external_id,
                "merchant_id": r.merchant_id,
                "provider": r.provider,
                "amount": r.amount,
                "currency": r.currency,
                "status": r.status,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    # ── Decorate with merchant names + derived state (no N+1) ──────────────
    if items:
        merchant_ids_in_page = {i["merchant_id"] for i in items}
        merchants = {
            m.id: m.name
            for m in (
                await db.execute(
                    select(Merchant).where(Merchant.id.in_(merchant_ids_in_page))
                )
            ).scalars()
        }
        reconciled_ids = set()
        discrepancy_ids = set()
        pairs = [(i["record_type"], i["id"]) for i in items]
        rel_rows = (
            await db.execute(
                select(ReconciliationRelationship).where(
                    or_(
                        *[
                            or_(
                                and_(
                                    ReconciliationRelationship.source_entity_type == rt,
                                    ReconciliationRelationship.source_entity_id == rid,
                                ),
                                and_(
                                    ReconciliationRelationship.target_entity_type == rt,
                                    ReconciliationRelationship.target_entity_id == rid,
                                ),
                            )
                            for rt, rid in pairs
                        ]
                    )
                )
            )
        ).scalars().all()
        for rel in rel_rows:
            reconciled_ids.add((rel.source_entity_type, rel.source_entity_id))
            reconciled_ids.add((rel.target_entity_type, rel.target_entity_id))
        disc_rows = (
            await db.execute(
                select(Discrepancy).where(
                    or_(
                        *[
                            or_(
                                and_(
                                    Discrepancy.source_entity_type == rt,
                                    Discrepancy.source_entity_id == rid,
                                ),
                                and_(
                                    Discrepancy.related_entity_type == rt,
                                    Discrepancy.related_entity_id == rid,
                                ),
                            )
                            for rt, rid in pairs
                        ]
                    )
                )
            )
        ).scalars().all()
        for d in disc_rows:
            discrepancy_ids.add((d.source_entity_type, d.source_entity_id))
            if d.related_entity_type and d.related_entity_id:
                discrepancy_ids.add((d.related_entity_type, d.related_entity_id))

        for i in items:
            i["merchant_name"] = merchants.get(i["merchant_id"], "Unknown merchant")
            key = (i["record_type"], i["id"])
            i["reconciled"] = key in reconciled_ids
            i["has_discrepancy"] = key in discrepancy_ids

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "summary": summary,
    }


# ─── Detail ──────────────────────────────────────────────────────────────────


async def _resolve_record(db: AsyncSession, record_id: str):
    """Locate a financial record by id across the five tables."""
    for table, rtype in (
        (Payment, PAYMENT),
        (Refund, REFUND),
        (Settlement, SETTLEMENT),
        (BankTransaction, BANK_TRANSACTION),
        (Fee, FEE),
    ):
        result = await db.execute(select(table).where(table.id == record_id))
        obj = result.scalar_one_or_none()
        if obj is not None:
            return rtype, obj
    return None, None


async def _derived_state(db: AsyncSession, record_type: str, record_id: str) -> dict[str, Any]:
    """Reconciliation / discrepancy / investigation / action state for an entity."""
    rel_rows = (
        await db.execute(
            select(ReconciliationRelationship).where(
                or_(
                    and_(
                        ReconciliationRelationship.source_entity_type == record_type,
                        ReconciliationRelationship.source_entity_id == record_id,
                    ),
                    and_(
                        ReconciliationRelationship.target_entity_type == record_type,
                        ReconciliationRelationship.target_entity_id == record_id,
                    ),
                )
            )
        )
    ).scalars().all()
    run_ids = {r.run_id for r in rel_rows}
    runs = {}
    if run_ids:
        runs = {
            run.id: run
            for run in (
                await db.execute(select(ReconciliationRun).where(ReconciliationRun.id.in_(run_ids)))
            ).scalars()
        }
    reconciliation = [
        {
            "relationship_id": r.id,
            "relationship_type": r.relationship_type,
            "relationship_status": r.relationship_status.value if hasattr(r.relationship_status, "value") else str(r.relationship_status),
            "financial_status": r.financial_status.value if hasattr(r.financial_status, "value") else str(r.financial_status),
            "run_id": r.run_id,
            "run_status": (runs[r.run_id].status.value if r.run_id in runs and hasattr(runs[r.run_id].status, "value") else (runs[r.run_id].status if r.run_id in runs else "UNKNOWN")),
            "source_entity_type": r.source_entity_type,
            "source_entity_id": r.source_entity_id,
            "target_entity_type": r.target_entity_type,
            "target_entity_id": r.target_entity_id,
        }
        for r in rel_rows
    ]

    disc_rows = (
        await db.execute(
            select(Discrepancy).where(
                or_(
                    and_(
                        Discrepancy.source_entity_type == record_type,
                        Discrepancy.source_entity_id == record_id,
                    ),
                    and_(
                        Discrepancy.related_entity_type == record_type,
                        Discrepancy.related_entity_id == record_id,
                    ),
                )
            )
        )
    ).scalars().all()
    discrepancies = [
        {
            "id": d.id,
            "rule_code": d.rule_code,
            "discrepancy_type": d.discrepancy_type.value if hasattr(d.discrepancy_type, "value") else str(d.discrepancy_type),
            "severity": d.severity.value if hasattr(d.severity, "value") else str(d.severity),
            "expected_amount": d.expected_amount,
            "actual_amount": d.actual_amount,
            "difference_amount": d.difference_amount,
            "currency": d.currency,
            "run_id": d.run_id,
        }
        for d in disc_rows
    ]

    investigation = None
    action_requests: list[dict[str, Any]] = []
    executions: list[dict[str, Any]] = []
    if discrepancies:
        disc_ids = [d["id"] for d in discrepancies]
        inv_rows = (
            await db.execute(
                select(Investigation).where(Investigation.discrepancy_id.in_(disc_ids))
            )
        ).scalars().all()
        investigations = {inv.discrepancy_id: inv for inv in inv_rows}
        investigation = (
            {
                "id": inv.id,
                "discrepancy_id": inv.discrepancy_id,
                "status": inv.status.value if hasattr(inv.status, "value") else str(inv.status),
                "created_at": inv.created_at,
            }
            for inv in investigations.values()
        )
        investigation = next(iter(investigation), None)
        if investigations:
            ar_rows = (
                await db.execute(
                    select(ActionRequest).where(
                        or_(
                            ActionRequest.discrepancy_id.in_(disc_ids),
                            ActionRequest.investigation_id.in_([inv.id for inv in investigations.values()]),
                        )
                    )
                )
            ).scalars().all()
            action_requests = [
                {
                    "id": ar.id,
                    "investigation_id": ar.investigation_id,
                    "discrepancy_id": ar.discrepancy_id,
                    "action": ar.action,
                    "status": ar.status.value if hasattr(ar.status, "value") else str(ar.status),
                    "created_at": ar.created_at,
                }
                for ar in ar_rows
            ]
            if action_requests:
                ex_rows = (
                    await db.execute(
                        select(ActionExecution).where(
                            ActionExecution.action_request_id.in_([a["id"] for a in action_requests])
                        )
                    )
                ).scalars().all()
                executions = [
                    {
                        "id": ex.id,
                        "action_request_id": ex.action_request_id,
                        "status": ex.status.value if hasattr(ex.status, "value") else str(ex.status),
                        "execution_type": ex.execution_type,
                        "adapter": ex.adapter,
                        "requested_at": ex.requested_at,
                        "error_code": ex.error_code,
                    }
                    for ex in ex_rows
                ]

    return {
        "reconciliation": reconciliation,
        "discrepancies": discrepancies,
        "investigation": investigation,
        "action_requests": action_requests,
        "executions": executions,
    }


async def get_transaction_detail(db: AsyncSession, record_id: str) -> Optional[dict[str, Any]]:
    record_type, obj = await _resolve_record(db, record_id)
    if obj is None:
        return None

    merchant = (
        await db.execute(select(Merchant).where(Merchant.id == obj.merchant_id))
    ).scalar_one_or_none()

    related: list[dict[str, Any]] = []
    order_ref = None
    customer_ref = None

    if record_type == PAYMENT:
        payment: Payment = obj
        order_obj = (
            await db.execute(
                select(Order)
                .options(selectinload(Order.customer))
                .where(Order.id == payment.order_id)
            )
        ).scalar_one_or_none()
        if order_obj:
            order_ref = {
                "id": order_obj.id,
                "external_id": order_obj.external_id,
                "status": order_obj.status,
                "amount": order_obj.amount,
                "currency": order_obj.currency,
            }
            if order_obj.customer:
                customer_ref = {
                    "id": order_obj.customer.id,
                    "display_name": order_obj.customer.display_name,
                }
        refunds = (
            await db.execute(select(Refund).where(Refund.payment_id == payment.id))
        ).scalars().all()
        fees = (
            await db.execute(select(Fee).where(Fee.payment_id == payment.id))
        ).scalars().all()
        for r in refunds:
            related.append(
                {
                    "id": r.id,
                    "record_type": REFUND,
                    "amount": r.amount,
                    "currency": r.currency,
                    "status": r.status,
                    "created_at": r.created_at,
                }
            )
        for f in fees:
            related.append(
                {
                    "id": f.id,
                    "record_type": FEE,
                    "amount": f.amount,
                    "currency": f.currency,
                    "status": f.fee_type,
                    "created_at": f.created_at,
                }
            )
    elif record_type == REFUND:
        refund: Refund = obj
        parent = (
            await db.execute(select(Payment).where(Payment.id == refund.payment_id))
        ).scalar_one_or_none()
        if parent:
            related.append(
                {
                    "id": parent.id,
                    "record_type": PAYMENT,
                    "amount": parent.amount,
                    "currency": parent.currency,
                    "status": parent.status,
                    "created_at": parent.created_at,
                }
            )
    elif record_type == SETTLEMENT:
        settlement: Settlement = obj
        items = (
            await db.execute(
                select(SettlementItem)
                .options(selectinload(SettlementItem.payment))
                .where(SettlementItem.settlement_id == settlement.id)
            )
        ).scalars().all()
        for si in items:
            related.append(
                {
                    "id": si.payment_id,
                    "record_type": PAYMENT,
                    "amount": si.amount,
                    "currency": si.currency,
                    "status": si.payment.status if si.payment else None,
                    "created_at": si.payment.created_at if si.payment else None,
                }
            )
        bank_rows = (
            await db.execute(
                select(BankTransaction).where(BankTransaction.settlement_id == settlement.id)
            )
        ).scalars().all()
        for btx in bank_rows:
            related.append(
                {
                    "id": btx.id,
                    "record_type": BANK_TRANSACTION,
                    "amount": btx.amount,
                    "currency": btx.currency,
                    "status": btx.status,
                    "created_at": btx.created_at,
                }
            )
    elif record_type == BANK_TRANSACTION:
        bank: BankTransaction = obj
        if bank.settlement_id:
            settlement = (
                await db.execute(select(Settlement).where(Settlement.id == bank.settlement_id))
            ).scalar_one_or_none()
            if settlement:
                related.append(
                    {
                        "id": settlement.id,
                        "record_type": SETTLEMENT,
                        "amount": settlement.expected_net_amount,
                        "currency": settlement.currency,
                        "status": settlement.status,
                        "created_at": settlement.created_at,
                    }
                )
    elif record_type == FEE:
        fee: Fee = obj
        if fee.payment_id:
            payment = (
                await db.execute(select(Payment).where(Payment.id == fee.payment_id))
            ).scalar_one_or_none()
            if payment:
                related.append(
                    {
                        "id": payment.id,
                        "record_type": PAYMENT,
                        "amount": payment.amount,
                        "currency": payment.currency,
                        "status": payment.status,
                        "created_at": payment.created_at,
                    }
                )
        if fee.settlement_id:
            settlement = (
                await db.execute(select(Settlement).where(Settlement.id == fee.settlement_id))
            ).scalar_one_or_none()
            if settlement:
                related.append(
                    {
                        "id": settlement.id,
                        "record_type": SETTLEMENT,
                        "amount": settlement.expected_net_amount,
                        "currency": settlement.currency,
                        "status": settlement.status,
                        "created_at": settlement.created_at,
                    }
                )

    derived = await _derived_state(db, record_type, record_id)

    return {
        "id": obj.id,
        "record_type": record_type,
        "external_id": obj.external_id,
        "merchant": {"id": obj.merchant_id, "name": merchant.name if merchant else "Unknown merchant"},
        "provider": getattr(obj, "provider", None) or getattr(obj, "bank_provider", None),
        "amount": obj.expected_net_amount if record_type == SETTLEMENT else obj.amount,
        "currency": obj.currency,
        "status": getattr(obj, "status", None) or getattr(obj, "fee_type", "N/A"),
        "created_at": obj.created_at,
        "updated_at": getattr(obj, "updated_at", None),
        "order": order_ref,
        "customer": customer_ref,
        "related": related,
        "reconciliation": derived["reconciliation"],
        "discrepancies": derived["discrepancies"],
        "investigation": derived["investigation"],
        "action_requests": derived["action_requests"],
        "executions": derived["executions"],
    }


# ─── Lineage ─────────────────────────────────────────────────────────────────


async def get_transaction_lineage(db: AsyncSession, record_id: str) -> Optional[dict[str, Any]]:
    """Deterministic lineage: SOURCE financial facts + DERIVED state nodes."""
    record_type, obj = await _resolve_record(db, record_id)
    if obj is None:
        return None

    nodes: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    def add(kind, node_id, label, role="SOURCE", status=None, amount=None, currency=None, ts=None, detail=None):
        nodes.append(
            {
                "kind": kind,
                "role": role,
                "id": node_id,
                "label": label,
                "status": status,
                "amount": amount,
                "currency": currency,
                "timestamp": ts,
                "detail": detail or {},
            }
        )

    # ── SOURCE facts ───────────────────────────────────────────────────────
    if record_type == PAYMENT:
        payment: Payment = obj
        order_obj = (
            await db.execute(
                select(Order).options(selectinload(Order.customer)).where(Order.id == payment.order_id)
            )
        ).scalar_one_or_none()
        if order_obj:
            add("ORDER", order_obj.id, f"Order · {order_obj.id[:8]}", status=order_obj.status, amount=order_obj.amount, currency=order_obj.currency, ts=order_obj.created_at)
        add("PAYMENT", payment.id, f"Payment · {payment.id[:8]}", status=payment.status, amount=payment.amount, currency=payment.currency, ts=payment.created_at, detail={"provider": payment.provider, "external_id": payment.external_id})
        refunds = (await db.execute(select(Refund).where(Refund.payment_id == payment.id))).scalars().all()
        for r in refunds:
            add("REFUND", r.id, f"Refund · {r.id[:8]}", status=r.status, amount=r.amount, currency=r.currency, ts=r.created_at)
        fees = (await db.execute(select(Fee).where(Fee.payment_id == payment.id))).scalars().all()
        for fee in fees:
            add("FEE", fee.id, f"Fee · {fee.id[:8]}", status=fee.fee_type, amount=fee.amount, currency=fee.currency, ts=fee.created_at)
        items = (
            await db.execute(
                select(SettlementItem).where(SettlementItem.payment_id == payment.id)
            )
        ).scalars().all()
        for si in items:
            add("SETTLEMENT_ITEM", si.id, f"Settlement Item · {si.id[:8]}", status="LINKED", amount=si.amount, currency=si.currency, ts=si.created_at, detail={"settlement_id": si.settlement_id})
        if items:
            settlements = (
                await db.execute(
                    select(Settlement)
                    .options(selectinload(Settlement.bank_transactions))
                    .where(Settlement.id.in_([si.settlement_id for si in items]))
                )
            ).scalars().all()
            for settle in settlements:
                add("SETTLEMENT", settle.id, f"Settlement · {settle.id[:8]}", status=settle.status, amount=settle.expected_net_amount, currency=settle.currency, ts=settle.settlement_date, detail={"gross": settle.gross_amount, "fees": settle.fee_amount, "adjustments": settle.adjustment_amount})
                for btx in settle.bank_transactions:
                    add("BANK_TRANSACTION", btx.id, f"Bank Transaction · {btx.id[:8]}", status=btx.status, amount=btx.amount, currency=btx.currency, ts=btx.transaction_date, detail={"provider": btx.bank_provider, "type": btx.transaction_type})
    elif record_type == SETTLEMENT:
        settlement: Settlement = obj
        add("SETTLEMENT", settlement.id, f"Settlement · {settlement.id[:8]}", status=settlement.status, amount=settlement.expected_net_amount, currency=settlement.currency, ts=settlement.settlement_date, detail={"gross": settlement.gross_amount, "fees": settlement.fee_amount, "adjustments": settlement.adjustment_amount})
        items = (
            await db.execute(
                select(SettlementItem)
                .options(selectinload(SettlementItem.payment))
                .where(SettlementItem.settlement_id == settlement.id)
            )
        ).scalars().all()
        for si in items:
            if si.payment:
                add("PAYMENT", si.payment.id, f"Payment · {si.payment.id[:8]}", status=si.payment.status, amount=si.amount, currency=si.currency, ts=si.payment.created_at, detail={"provider": si.payment.provider})
        bank_rows = (
            await db.execute(
                select(BankTransaction).where(BankTransaction.settlement_id == settlement.id)
            )
        ).scalars().all()
        for btx in bank_rows:
            add("BANK_TRANSACTION", btx.id, f"Bank Transaction · {btx.id[:8]}", status=btx.status, amount=btx.amount, currency=btx.currency, ts=btx.transaction_date, detail={"provider": btx.bank_provider, "type": btx.transaction_type})
    elif record_type == REFUND:
        refund: Refund = obj
        add("REFUND", refund.id, f"Refund · {refund.id[:8]}", status=refund.status, amount=refund.amount, currency=refund.currency, ts=refund.created_at, detail={"reason": refund.reason, "provider": refund.provider})
        payment = (await db.execute(select(Payment).where(Payment.id == refund.payment_id))).scalar_one_or_none()
        if payment:
            add("PAYMENT", payment.id, f"Payment · {payment.id[:8]}", status=payment.status, amount=payment.amount, currency=payment.currency, ts=payment.created_at)
    elif record_type == BANK_TRANSACTION:
        bank: BankTransaction = obj
        add("BANK_TRANSACTION", bank.id, f"Bank Transaction · {bank.id[:8]}", status=bank.status, amount=bank.amount, currency=bank.currency, ts=bank.transaction_date, detail={"provider": bank.bank_provider, "type": bank.transaction_type, "description": bank.description})
        if bank.settlement_id:
            settlement = (await db.execute(select(Settlement).where(Settlement.id == bank.settlement_id))).scalar_one_or_none()
            if settlement:
                add("SETTLEMENT", settlement.id, f"Settlement · {settlement.id[:8]}", status=settlement.status, amount=settlement.expected_net_amount, currency=settlement.currency, ts=settlement.settlement_date)
    elif record_type == FEE:
        fee: Fee = obj
        add("FEE", fee.id, f"Fee · {fee.id[:8]}", status=fee.fee_type, amount=fee.amount, currency=fee.currency, ts=fee.created_at, detail={"fee_type": fee.fee_type, "provider": fee.provider})
        if fee.payment_id:
            payment = (await db.execute(select(Payment).where(Payment.id == fee.payment_id))).scalar_one_or_none()
            if payment:
                add("PAYMENT", payment.id, f"Payment · {payment.id[:8]}", status=payment.status, amount=payment.amount, currency=payment.currency, ts=payment.created_at)

    # ── DERIVED state (reconciliation / exception / action) ────────────────
    derived = await _derived_state(db, record_type, record_id)
    for rel in derived["reconciliation"]:
        add(
            "RECONCILIATION",
            rel["relationship_id"],
            f"Reconciliation · {rel['relationship_type'].replace('_', ' ').title()}",
            role="DERIVED",
            status=rel["relationship_status"],
            ts=None,
            detail={
                "financial_status": rel["financial_status"],
                "run_status": rel["run_status"],
                "source": f"{rel['source_entity_type']} {rel['source_entity_id'][:8]}",
                "target": f"{rel['target_entity_type']} {rel['target_entity_id'][:8]}",
            },
        )
    for d in derived["discrepancies"]:
        add(
            "DISCREPANCY",
            d["id"],
            f"Discrepancy · {d['id'][:8]}",
            role="DERIVED",
            status=d["severity"],
            amount=d["difference_amount"],
            currency=d["currency"],
            ts=None,
            detail={"rule_code": d["rule_code"], "discrepancy_type": d["discrepancy_type"]},
        )
    if derived["investigation"]:
        inv = derived["investigation"]
        add("INVESTIGATION", inv["id"], f"Investigation · {inv['id'][:8]}", role="DERIVED", status=inv["status"], ts=inv["created_at"])
    for ar in derived["action_requests"]:
        add("ACTION_REQUEST", ar["id"], f"Action Request · {ar['id'][:8]}", role="DERIVED", status=ar["status"], ts=ar["created_at"], detail={"action": ar["action"]})
    for ex in derived["executions"]:
        add("ACTION_EXECUTION", ex["id"], f"Execution · {ex['id'][:8]}", role="DERIVED", status=ex["status"], ts=ex["requested_at"], detail={"type": ex["execution_type"], "adapter": ex["adapter"]})

    return {"record_type": record_type, "record_id": record_id, "nodes": nodes}