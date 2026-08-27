import asyncio
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from packages.utils.id_generator import generate_id
from database.connection import get_session
from database.models import (
    Merchant, Customer, Order, Payment, Refund, Fee, 
    Settlement, SettlementItem, BankTransaction, FinancialEvent
)
from packages.schemas.enums import (
    OrderStatus, PaymentStatus, RefundStatus, FeeType, 
    SettlementStatus, BankTransactionType, BankTransactionStatus, EventType
)

SEED = 42

class DataGenerator:
    def __init__(self, session: AsyncSession):
        self.session = session
        random.seed(SEED)
        
    def _dt(self, days_ago: int = 0, hours: int = 0) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days_ago, hours=hours)
        
    def _uuid(self):
        return str(uuid.uuid4())

    async def generate(self):
        # 1. Create Base Merchant & Customer
        merchant_id = generate_id("mch")
        merchant = Merchant(
            id=merchant_id,
            external_id=f"ext_{merchant_id}",
            name="FinOps Synthetic Merchant",
            default_currency="USD"
        )
        self.session.add(merchant)

        customer_id = generate_id("cus")
        customer = Customer(
            id=customer_id,
            external_id=f"ext_{customer_id}",
            merchant_id=merchant_id,
            display_name="Alice User"
        )
        self.session.add(customer)
        
        await self.session.commit()
        
        # We will implement the 11 scenarios in subsequent PRs/commits to keep this file focused.
        # Let's start with Scenario 1: Perfect Match Flow
        
        # -- SCENARIO 1: Perfect Match Flow --
        order_1 = Order(
            id=generate_id("ord"),
            external_id=self._uuid(),
            merchant_id=merchant_id,
            customer_id=customer_id,
            amount=Decimal("100.00"),
            currency="USD",
            status=OrderStatus.PAID
        )
        self.session.add(order_1)
        
        payment_1 = Payment(
            id=generate_id("pay"),
            external_id=self._uuid(),
            merchant_id=merchant_id,
            order_id=order_1.id,
            provider="MOCK_GATEWAY",
            amount=Decimal("100.00"),
            currency="USD",
            status=PaymentStatus.CAPTURED,
            payment_method_type="CARD",
            processed_at=self._dt(days_ago=2)
        )
        self.session.add(payment_1)
        
        fee_1 = Fee(
            id=generate_id("fee"),
            external_id=self._uuid(),
            merchant_id=merchant_id,
            payment_id=payment_1.id,
            fee_type=FeeType.PROCESSING,
            amount=Decimal("2.90"),
            currency="USD",
            provider="MOCK_GATEWAY"
        )
        self.session.add(fee_1)
        
        settlement_1 = Settlement(
            id=generate_id("set"),
            external_id=self._uuid(),
            merchant_id=merchant_id,
            provider="MOCK_GATEWAY",
            gross_amount=Decimal("100.00"),
            fee_amount=Decimal("2.90"),
            adjustment_amount=Decimal("0.00"),
            expected_net_amount=Decimal("97.10"),
            actual_settled_amount=Decimal("97.10"),
            currency="USD",
            settlement_date=self._dt(days_ago=1),
            status=SettlementStatus.SETTLED
        )
        self.session.add(settlement_1)
        
        si_1 = SettlementItem(
            id=generate_id("sit"),
            settlement_id=settlement_1.id,
            payment_id=payment_1.id,
            amount=Decimal("100.00"),
            currency="USD"
        )
        self.session.add(si_1)
        
        bt_1 = BankTransaction(
            id=generate_id("btx"),
            external_id=self._uuid(),
            merchant_id=merchant_id,
            bank_provider="MOCK_BANK",
            settlement_id=settlement_1.id,
            amount=Decimal("97.10"),
            currency="USD",
            transaction_type=BankTransactionType.CREDIT,
            transaction_date=self._dt(days_ago=1),
            status=BankTransactionStatus.POSTED
        )
        self.session.add(bt_1)
        
        await self.session.commit()

async def run_seed():
    async for session in get_session():
        generator = DataGenerator(session)
        await generator.generate()
        print("Data generation complete.")

if __name__ == "__main__":
    asyncio.run(run_seed())
