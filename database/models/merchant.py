from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base, TimestampMixin


class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=True, unique=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")
    status: Mapped[str] = mapped_column(String, nullable=False, default="ACTIVE")

    customers: Mapped[list["Customer"]] = relationship("Customer", back_populates="merchant")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="merchant")
    payments: Mapped[list["Payment"]] = relationship("Payment", back_populates="merchant")
    settlements: Mapped[list["Settlement"]] = relationship("Settlement", back_populates="merchant")


class Customer(Base, TimestampMixin):
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    external_id: Mapped[str] = mapped_column(String, nullable=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)

    merchant: Mapped["Merchant"] = relationship("Merchant", back_populates="customers")
    orders: Mapped[list["Order"]] = relationship("Order", back_populates="customer")
