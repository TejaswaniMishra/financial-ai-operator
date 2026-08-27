import pytest
from decimal import Decimal
from services.ingestion.base import IngestionService

@pytest.mark.asyncio
async def test_validate_refund_domain_rules_valid(db_session):
    service = IngestionService(db_session)
    # Should not raise
    await service.validate_refund_domain_rules(Decimal("50.00"), Decimal("100.00"), "USD", "USD")

@pytest.mark.asyncio
async def test_validate_refund_domain_rules_exceeds_amount(db_session):
    service = IngestionService(db_session)
    with pytest.raises(ValueError, match="exceeds payment amount"):
        await service.validate_refund_domain_rules(Decimal("150.00"), Decimal("100.00"), "USD", "USD")

@pytest.mark.asyncio
async def test_validate_refund_domain_rules_currency_mismatch(db_session):
    service = IngestionService(db_session)
    with pytest.raises(ValueError, match="does not match payment currency"):
        await service.validate_refund_domain_rules(Decimal("50.00"), Decimal("100.00"), "EUR", "USD")

@pytest.mark.asyncio
async def test_validate_settlement_totals_valid(db_session):
    service = IngestionService(db_session)
    # gross - fee + adj = expected_net
    # 100 - 2 + 0 = 98
    await service.validate_settlement_totals(Decimal("100.00"), Decimal("2.00"), Decimal("0.00"), Decimal("98.00"))

@pytest.mark.asyncio
async def test_validate_settlement_totals_invalid(db_session):
    service = IngestionService(db_session)
    # 100 - 2 + 0 != 99
    with pytest.raises(ValueError, match="Settlement totals invalid"):
        await service.validate_settlement_totals(Decimal("100.00"), Decimal("2.00"), Decimal("0.00"), Decimal("99.00"))
