from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, Numeric, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from database.base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), nullable=False)
    
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="orders")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="orders")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="order")


class Payment(Base, TimestampMixin):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_payment_provider_ext_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False)
    
    provider: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    status: Mapped[str] = mapped_column(String, nullable=False)
    payment_method_type: Mapped[str] = mapped_column(String, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="payments")
    order: Mapped["Order"] = relationship("Order", back_populates="payments")
    refunds: Mapped[list["Refund"]] = relationship("Refund", back_populates="payment")
    fees: Mapped[list["Fee"]] = relationship("Fee", foreign_keys="[Fee.payment_id]", back_populates="payment")
    settlement_items: Mapped[list["SettlementItem"]] = relationship("SettlementItem", back_populates="payment")


class Refund(Base, TimestampMixin):
    __tablename__ = "refunds"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_refund_provider_ext_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="MOCK_GATEWAY")
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), nullable=False)
    
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    
    status: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    payment: Mapped["Payment"] = relationship("Payment", back_populates="refunds")


class Settlement(Base, TimestampMixin):
    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_settlement_provider_ext_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    
    gross_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    fee_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    adjustment_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False, default=0)
    expected_net_amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    actual_settled_amount: Mapped[Optional[float]] = mapped_column(Numeric(18, 4), nullable=True)
    
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    settlement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)

    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="settlements")
    items: Mapped[list["SettlementItem"]] = relationship("SettlementItem", back_populates="settlement")
    bank_transactions: Mapped[list["BankTransaction"]] = relationship("BankTransaction", back_populates="settlement")
    fees: Mapped[list["Fee"]] = relationship("Fee", foreign_keys="[Fee.settlement_id]", back_populates="settlement")


class SettlementItem(Base, TimestampMixin):
    __tablename__ = "settlement_items"
    
    id: Mapped[str] = mapped_column(String, primary_key=True)
    settlement_id: Mapped[str] = mapped_column(ForeignKey("settlements.id"), nullable=False)
    payment_id: Mapped[str] = mapped_column(ForeignKey("payments.id"), nullable=False)
    
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    settlement: Mapped["Settlement"] = relationship("Settlement", back_populates="items")
    payment: Mapped["Payment"] = relationship("Payment", back_populates="settlement_items")


class Fee(Base, TimestampMixin):
    __tablename__ = "fees"
    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_fee_provider_ext_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    
    payment_id: Mapped[Optional[str]] = mapped_column(ForeignKey("payments.id"), nullable=True)
    settlement_id: Mapped[Optional[str]] = mapped_column(ForeignKey("settlements.id"), nullable=True)
    
    fee_type: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)

    payment: Mapped[Optional["Payment"]] = relationship("Payment", back_populates="fees", foreign_keys=[payment_id])
    settlement: Mapped[Optional["Settlement"]] = relationship("Settlement", back_populates="fees", foreign_keys=[settlement_id])


class BankTransaction(Base, TimestampMixin):
    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint("bank_provider", "external_id", name="uq_banktx_provider_ext_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    bank_provider: Mapped[str] = mapped_column(String, nullable=False)
    settlement_id: Mapped[Optional[str]] = mapped_column(ForeignKey("settlements.id"), nullable=True)
    
    amount: Mapped[float] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String, nullable=False) # CREDIT, DEBIT
    
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)

    settlement: Mapped[Optional["Settlement"]] = relationship("Settlement", back_populates="bank_transactions")
