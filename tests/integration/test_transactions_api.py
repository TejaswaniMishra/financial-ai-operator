import pytest
from httpx import AsyncClient
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from decimal import Decimal

from apps.api.main import app
from database.models import Merchant, Payment, Order, Customer
from packages.schemas.enums import OrderStatus, PaymentStatus

@pytest.fixture
async def sample_transaction_data(db_session: AsyncSession):
    # Base setup
    m = Merchant(id="mch_test1", name="Test Merch", default_currency="USD")
    c = Customer(id="cus_test1", merchant_id="mch_test1", display_name="Test Customer")
    o = Order(
        id="ord_test1", merchant_id="mch_test1", customer_id="cus_test1",
        amount=Decimal("100.00"), currency="USD", status=OrderStatus.PAID
    )
    p = Payment(
        id="pay_test1", external_id="ext_pay_1", merchant_id="mch_test1", order_id="ord_test1",
        provider="MOCK_GATEWAY", amount=Decimal("100.00"), currency="USD", status=PaymentStatus.CAPTURED
    )
    
    db_session.add_all([m, c, o, p])
    await db_session.commit()
    return {"payment_id": "pay_test1", "merchant_id": "mch_test1"}

@pytest.mark.asyncio
async def test_list_payments(async_client: AsyncClient, sample_transaction_data, auth_headers):
    response = await async_client.get("/api/v1/transactions/payments", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["id"] == "pay_test1"
    
@pytest.mark.asyncio
async def test_get_payment_lineage(async_client: AsyncClient, sample_transaction_data, auth_headers):
    pid = sample_transaction_data["payment_id"]
    response = await async_client.get(f"/api/v1/transactions/payments/{pid}/lineage", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["order"]["id"] == "ord_test1"
    assert data["payment"]["id"] == pid
    assert data["payment"]["provider"] == "MOCK_GATEWAY"
    
@pytest.mark.asyncio
async def test_metrics_overview(async_client: AsyncClient, sample_transaction_data, auth_headers):
    response = await async_client.get("/api/v1/metrics/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    
    assert data["merchants"] >= 1
    assert data["payments"] >= 1
    assert data["total_volume"] >= 100.0
