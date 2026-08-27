from decimal import Decimal
import pytest
from packages.schemas.money import Currency, Money


def test_money_creation_with_decimal_and_string():
    m1 = Money(amount=Decimal("150.75"), currency=Currency.USD)
    m2 = Money(amount="150.75", currency=Currency.USD)
    m3 = Money(amount=100, currency=Currency.USD)

    assert m1.amount == Decimal("150.75")
    assert m2.amount == Decimal("150.75")
    assert m3.amount == Decimal("100")
    assert m1 == m2


def test_money_rejects_floats():
    """Verify that floats are strictly rejected to prevent financial rounding drift."""
    with pytest.raises(TypeError, match="Float is strictly forbidden"):
        Money(amount=150.75, currency=Currency.USD)  # type: ignore


def test_money_arithmetic_same_currency():
    m1 = Money(amount="100.50", currency=Currency.USD)
    m2 = Money(amount="50.25", currency=Currency.USD)

    # Addition
    sum_res = m1 + m2
    assert sum_res == Money(amount="150.75", currency=Currency.USD)

    # Subtraction
    sub_res = m1 - m2
    assert sub_res == Money(amount="50.25", currency=Currency.USD)

    # Multiplication by Decimal factor
    mul_res = m1 * Decimal("2")
    assert mul_res == Money(amount="201.00", currency=Currency.USD)


def test_money_rejects_cross_currency_arithmetic():
    """Verify that adding or subtracting mismatched currencies raises a ValueError."""
    usd = Money(amount="100.00", currency=Currency.USD)
    eur = Money(amount="100.00", currency=Currency.EUR)

    with pytest.raises(ValueError, match="Currency mismatch error"):
        _ = usd + eur

    with pytest.raises(ValueError, match="Currency mismatch error"):
        _ = usd - eur

    with pytest.raises(ValueError, match="Currency mismatch error"):
        _ = usd < eur


def test_money_bankers_rounding():
    # 2.5 rounded to 0 decimal places with half-even -> 2
    # 3.5 rounded to 0 decimal places with half-even -> 4
    m_even = Money(amount="2.5", currency=Currency.USD).round_to(0)
    m_odd = Money(amount="3.5", currency=Currency.USD).round_to(0)

    assert m_even.amount == Decimal("2")
    assert m_odd.amount == Decimal("4")


def test_money_formatting():
    m = Money(amount="1234567.89", currency=Currency.USD)
    assert m.to_formatted_string() == "$1,234,567.89"
