import asyncio
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from packages.utils.id_generator import generate_id
from database.connection import get_async_db
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
        
        # 1.5. Seed Roles Idempotently
        from sqlalchemy.future import select
        from database.models.identity import Role, RoleName

        for role_name in RoleName:
            stmt = select(Role).where(Role.name == role_name)
            existing_role = (await self.session.execute(stmt)).scalar_one_or_none()
            if not existing_role:
                new_role = Role(
                    name=role_name,
                    description=f"System generated {role_name.value} role"
                )
                self.session.add(new_role)
        
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
        
        # -- SCENARIO 2: Settlement containing multiple payments --
        # We will create two orders and two payments, then one settlement
        order_2a = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("50.00"), currency="USD", status=OrderStatus.PAID)
        order_2b = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("60.00"), currency="USD", status=OrderStatus.PAID)
        self.session.add_all([order_2a, order_2b])
        
        pay_2a = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_2a.id, provider="MOCK_GATEWAY", amount=Decimal("50.00"), currency="USD", status=PaymentStatus.CAPTURED, processed_at=self._dt(days_ago=2))
        pay_2b = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_2b.id, provider="MOCK_GATEWAY", amount=Decimal("60.00"), currency="USD", status=PaymentStatus.CAPTURED, processed_at=self._dt(days_ago=2))
        self.session.add_all([pay_2a, pay_2b])
        
        fee_2 = Fee(id=generate_id("fee"), external_id=self._uuid(), merchant_id=merchant_id, fee_type=FeeType.PROCESSING, amount=Decimal("3.00"), currency="USD", provider="MOCK_GATEWAY")
        self.session.add(fee_2)
        
        set_2 = Settlement(
            id=generate_id("set"), external_id=self._uuid(), merchant_id=merchant_id, provider="MOCK_GATEWAY",
            gross_amount=Decimal("110.00"), fee_amount=Decimal("3.00"), adjustment_amount=Decimal("0.00"),
            expected_net_amount=Decimal("107.00"), actual_settled_amount=Decimal("107.00"), currency="USD",
            settlement_date=self._dt(days_ago=1), status=SettlementStatus.SETTLED
        )
        self.session.add(set_2)
        fee_2.settlement_id = set_2.id
        
        si_2a = SettlementItem(id=generate_id("sit"), settlement_id=set_2.id, payment_id=pay_2a.id, amount=Decimal("50.00"), currency="USD")
        si_2b = SettlementItem(id=generate_id("sit"), settlement_id=set_2.id, payment_id=pay_2b.id, amount=Decimal("60.00"), currency="USD")
        self.session.add_all([si_2a, si_2b])
        
        bt_2 = BankTransaction(
            id=generate_id("btx"), external_id=self._uuid(), merchant_id=merchant_id, bank_provider="MOCK_BANK",
            settlement_id=set_2.id, amount=Decimal("107.00"), currency="USD", transaction_type=BankTransactionType.CREDIT,
            transaction_date=self._dt(days_ago=1), status=BankTransactionStatus.POSTED
        )
        self.session.add(bt_2)

        # -- SCENARIO 3: Settlement with a fee difference --
        # Gross = 100, Expected Fee = 2, Expected Net = 98. Actual Settled = 97 (Fee difference of 1)
        order_3 = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("100.00"), currency="USD", status=OrderStatus.PAID)
        self.session.add(order_3)
        pay_3 = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_3.id, provider="MOCK_GATEWAY", amount=Decimal("100.00"), currency="USD", status=PaymentStatus.CAPTURED, processed_at=self._dt(days_ago=2))
        self.session.add(pay_3)
        set_3 = Settlement(
            id=generate_id("set"), external_id=self._uuid(), merchant_id=merchant_id, provider="MOCK_GATEWAY",
            gross_amount=Decimal("100.00"), fee_amount=Decimal("2.00"), adjustment_amount=Decimal("0.00"),
            expected_net_amount=Decimal("98.00"), actual_settled_amount=Decimal("97.00"), currency="USD",
            settlement_date=self._dt(days_ago=1), status=SettlementStatus.DISCREPANT
        )
        self.session.add(set_3)
        si_3 = SettlementItem(id=generate_id("sit"), settlement_id=set_3.id, payment_id=pay_3.id, amount=Decimal("100.00"), currency="USD")
        self.session.add(si_3)
        bt_3 = BankTransaction(
            id=generate_id("btx"), external_id=self._uuid(), merchant_id=merchant_id, bank_provider="MOCK_BANK",
            settlement_id=set_3.id, amount=Decimal("97.00"), currency="USD", transaction_type=BankTransactionType.CREDIT,
            transaction_date=self._dt(days_ago=1), status=BankTransactionStatus.POSTED
        )
        self.session.add(bt_3)

        # -- SCENARIO 4: Payment with missing bank transaction --
        order_4 = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("75.00"), currency="USD", status=OrderStatus.PAID)
        self.session.add(order_4)
        pay_4 = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_4.id, provider="MOCK_GATEWAY", amount=Decimal("75.00"), currency="USD", status=PaymentStatus.CAPTURED, processed_at=self._dt(days_ago=2))
        self.session.add(pay_4)
        set_4 = Settlement(
            id=generate_id("set"), external_id=self._uuid(), merchant_id=merchant_id, provider="MOCK_GATEWAY",
            gross_amount=Decimal("75.00"), fee_amount=Decimal("1.50"), adjustment_amount=Decimal("0.00"),
            expected_net_amount=Decimal("73.50"), actual_settled_amount=None, currency="USD",
            settlement_date=self._dt(days_ago=1), status=SettlementStatus.PENDING
        )
        self.session.add(set_4)
        si_4 = SettlementItem(id=generate_id("sit"), settlement_id=set_4.id, payment_id=pay_4.id, amount=Decimal("75.00"), currency="USD")
        self.session.add(si_4)
        # Missing BankTransaction

        # -- SCENARIO 5: Duplicate ingestion handled by IngestionService --
        # Handled in tests by inserting the same fingerprint twice

        # -- SCENARIO 6: Payment followed by partial refund --
        order_6 = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("120.00"), currency="USD", status=OrderStatus.PAID)
        self.session.add(order_6)
        pay_6 = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_6.id, provider="MOCK_GATEWAY", amount=Decimal("120.00"), currency="USD", status=PaymentStatus.PARTIALLY_REFUNDED, processed_at=self._dt(days_ago=3))
        self.session.add(pay_6)
        ref_6 = Refund(id=generate_id("ref"), external_id=self._uuid(), merchant_id=merchant_id, payment_id=pay_6.id, provider="MOCK_GATEWAY", amount=Decimal("40.00"), currency="USD", status=RefundStatus.SUCCEEDED, reason="CUSTOMER_REQUEST", processed_at=self._dt(days_ago=2))
        self.session.add(ref_6)

        # -- SCENARIO 7: Failed payment --
        order_7 = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("90.00"), currency="USD", status=OrderStatus.CREATED)
        self.session.add(order_7)
        pay_7 = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_7.id, provider="MOCK_GATEWAY", amount=Decimal("90.00"), currency="USD", status=PaymentStatus.FAILED, processed_at=self._dt(days_ago=2))
        self.session.add(pay_7)

        # -- SCENARIO 8: Settlement arriving later than expected --
        order_8 = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("80.00"), currency="USD", status=OrderStatus.PAID)
        self.session.add(order_8)
        pay_8 = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_8.id, provider="MOCK_GATEWAY", amount=Decimal("80.00"), currency="USD", status=PaymentStatus.CAPTURED, processed_at=self._dt(days_ago=10))
        self.session.add(pay_8)
        set_8 = Settlement(
            id=generate_id("set"), external_id=self._uuid(), merchant_id=merchant_id, provider="MOCK_GATEWAY",
            gross_amount=Decimal("80.00"), fee_amount=Decimal("2.00"), adjustment_amount=Decimal("0.00"),
            expected_net_amount=Decimal("78.00"), actual_settled_amount=Decimal("78.00"), currency="USD",
            settlement_date=self._dt(days_ago=1), # 9 days late
            status=SettlementStatus.SETTLED
        )
        self.session.add(set_8)
        si_8 = SettlementItem(id=generate_id("sit"), settlement_id=set_8.id, payment_id=pay_8.id, amount=Decimal("80.00"), currency="USD")
        self.session.add(si_8)
        bt_8 = BankTransaction(
            id=generate_id("btx"), external_id=self._uuid(), merchant_id=merchant_id, bank_provider="MOCK_BANK",
            settlement_id=set_8.id, amount=Decimal("78.00"), currency="USD", transaction_type=BankTransactionType.CREDIT,
            transaction_date=self._dt(days_ago=1), status=BankTransactionStatus.POSTED
        )
        self.session.add(bt_8)

        # -- SCENARIO 9: Bank transaction with mismatching amount --
        order_9 = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("200.00"), currency="USD", status=OrderStatus.PAID)
        self.session.add(order_9)
        pay_9 = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_9.id, provider="MOCK_GATEWAY", amount=Decimal("200.00"), currency="USD", status=PaymentStatus.CAPTURED, processed_at=self._dt(days_ago=2))
        self.session.add(pay_9)
        set_9 = Settlement(
            id=generate_id("set"), external_id=self._uuid(), merchant_id=merchant_id, provider="MOCK_GATEWAY",
            gross_amount=Decimal("200.00"), fee_amount=Decimal("5.00"), adjustment_amount=Decimal("0.00"),
            expected_net_amount=Decimal("195.00"), actual_settled_amount=Decimal("190.00"), currency="USD",
            settlement_date=self._dt(days_ago=1), status=SettlementStatus.DISCREPANT
        )
        self.session.add(set_9)
        si_9 = SettlementItem(id=generate_id("sit"), settlement_id=set_9.id, payment_id=pay_9.id, amount=Decimal("200.00"), currency="USD")
        self.session.add(si_9)
        bt_9 = BankTransaction(
            id=generate_id("btx"), external_id=self._uuid(), merchant_id=merchant_id, bank_provider="MOCK_BANK",
            settlement_id=set_9.id, amount=Decimal("190.00"), currency="USD", transaction_type=BankTransactionType.CREDIT,
            transaction_date=self._dt(days_ago=1), status=BankTransactionStatus.POSTED
        )
        self.session.add(bt_9)

        # -- SCENARIO 10: Currency mismatch (Created via Ingestion Exception later in tests, but let's seed a discrepant one here) --
        # E.g. Bank transaction in EUR for USD settlement
        order_10 = Order(id=generate_id("ord"), external_id=self._uuid(), merchant_id=merchant_id, customer_id=customer_id, amount=Decimal("300.00"), currency="USD", status=OrderStatus.PAID)
        self.session.add(order_10)
        pay_10 = Payment(id=generate_id("pay"), external_id=self._uuid(), merchant_id=merchant_id, order_id=order_10.id, provider="MOCK_GATEWAY", amount=Decimal("300.00"), currency="USD", status=PaymentStatus.CAPTURED, processed_at=self._dt(days_ago=2))
        self.session.add(pay_10)
        set_10 = Settlement(
            id=generate_id("set"), external_id=self._uuid(), merchant_id=merchant_id, provider="MOCK_GATEWAY",
            gross_amount=Decimal("300.00"), fee_amount=Decimal("10.00"), adjustment_amount=Decimal("0.00"),
            expected_net_amount=Decimal("290.00"), actual_settled_amount=Decimal("275.50"), currency="USD",
            settlement_date=self._dt(days_ago=1), status=SettlementStatus.DISCREPANT
        )
        self.session.add(set_10)
        si_10 = SettlementItem(id=generate_id("sit"), settlement_id=set_10.id, payment_id=pay_10.id, amount=Decimal("300.00"), currency="USD")
        self.session.add(si_10)
        bt_10 = BankTransaction(
            id=generate_id("btx"), external_id=self._uuid(), merchant_id=merchant_id, bank_provider="MOCK_BANK",
            settlement_id=set_10.id, amount=Decimal("275.50"), currency="EUR", transaction_type=BankTransactionType.CREDIT,
            transaction_date=self._dt(days_ago=1), status=BankTransactionStatus.POSTED
        )
        self.session.add(bt_10)

        # -- SCENARIO 11: Orphan transaction (Ingestion exception) --
        # We will test this explicitly in integration tests using IngestionService.

        await self.session.commit()

async def run_seed():
    async for session in get_async_db():
        generator = DataGenerator(session)
        await generator.generate()
        print("Data generation complete.")

if __name__ == "__main__":
    asyncio.run(run_seed())
