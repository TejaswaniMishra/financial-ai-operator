from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from decimal import Decimal

from packages.schemas.enums import (
    OrderStatus,
    PaymentStatus,
    RefundStatus,
    FeeType,
    SettlementStatus,
    BankTransactionType,
    BankTransactionStatus,
    EventType,
    IngestionStatus,
)


class DomainBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class MerchantSchema(DomainBase):
    id: str
    external_id: Optional[str]
    name: str
    default_currency: str
    timezone: str
    status: str
    created_at: datetime
    updated_at: datetime


class CustomerSchema(DomainBase):
    id: str
    external_id: Optional[str]
    merchant_id: str
    display_name: str
    created_at: datetime
    updated_at: datetime


class OrderSchema(DomainBase):
    id: str
    external_id: Optional[str]
    merchant_id: str
    customer_id: str
    amount: Decimal
    currency: str
    status: OrderStatus
    created_at: datetime
    updated_at: datetime


class PaymentSchema(DomainBase):
    id: str
    external_id: str
    merchant_id: str
    order_id: str
    provider: str
    amount: Decimal
    currency: str
    status: PaymentStatus
    payment_method_type: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class RefundSchema(DomainBase):
    id: str
    external_id: str
    merchant_id: str
    payment_id: str
    provider: str
    amount: Decimal
    currency: str
    status: RefundStatus
    reason: Optional[str]
    processed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class FeeSchema(DomainBase):
    id: str
    external_id: str
    merchant_id: str
    payment_id: Optional[str]
    settlement_id: Optional[str]
    fee_type: FeeType
    amount: Decimal
    currency: str
    provider: str
    created_at: datetime
    updated_at: datetime


class SettlementItemSchema(DomainBase):
    id: str
    settlement_id: str
    payment_id: str
    amount: Decimal
    currency: str
    created_at: datetime
    updated_at: datetime


class SettlementSchema(DomainBase):
    id: str
    external_id: str
    merchant_id: str
    provider: str
    gross_amount: Decimal
    fee_amount: Decimal
    adjustment_amount: Decimal
    expected_net_amount: Decimal
    actual_settled_amount: Optional[Decimal]
    currency: str
    settlement_date: datetime
    status: SettlementStatus
    created_at: datetime
    updated_at: datetime


class BankTransactionSchema(DomainBase):
    id: str
    external_id: str
    merchant_id: str
    bank_provider: str
    settlement_id: Optional[str]
    amount: Decimal
    currency: str
    transaction_type: BankTransactionType
    transaction_date: datetime
    description: Optional[str]
    status: BankTransactionStatus
    created_at: datetime
    updated_at: datetime


class IngestionRecordSchema(DomainBase):
    id: str
    provider: str
    external_id: str
    entity_type: str
    raw_payload: dict
    fingerprint: str
    status: IngestionStatus
    created_at: datetime
    updated_at: datetime


class FinancialEventSchema(DomainBase):
    id: str
    merchant_id: str
    entity_type: str
    entity_id: str
    event_type: EventType
    amount: Optional[Decimal]
    currency: Optional[str]
    metadata_payload: Optional[dict]
    timestamp: datetime
