from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum
from typing import Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator


class Currency(str, Enum):
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    INR = "INR"
    CAD = "CAD"
    AUD = "AUD"
    JPY = "JPY"

    @classmethod
    def default(cls) -> "Currency":
        return cls.USD


class Money(BaseModel):
    """
    Immutable Financial Value Object.
    
    Guarantees:
    1. Amount is strictly Decimal (never float).
    2. Explicit Currency code is always present.
    3. Arithmetic validates currency compatibility.
    4. Rounding defaults to Banker's Rounding (ROUND_HALF_EVEN).
    """
    amount: Decimal = Field(..., description="Exact monetary amount using Decimal")
    currency: Currency = Field(default=Currency.USD, description="Explicit 3-letter ISO currency code")

    model_config = {
        "frozen": True,
        "json_encoders": {
            Decimal: lambda v: str(v)
        }
    }

    @field_validator("amount", mode="before")
    @classmethod
    def validate_and_convert_amount(cls, v: Any) -> Decimal:
        if isinstance(v, float):
            raise TypeError(
                f"Float is strictly forbidden for monetary calculations to prevent precision loss. "
                f"Received float: {v}. Pass a Decimal or string representation instead."
            )
        if isinstance(v, (int, str)):
            return Decimal(str(v))
        if isinstance(v, Decimal):
            return v
        raise TypeError(f"Cannot construct Money amount from type {type(v).__name__}")

    def __add__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        self._assert_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, factor: Union[Decimal, int]) -> "Money":
        if isinstance(factor, float):
            raise TypeError(f"Float factor {factor} forbidden. Use Decimal or int.")
        return Money(amount=self.amount * Decimal(str(factor)), currency=self.currency)

    def __neg__(self) -> "Money":
        return Money(amount=-self.amount, currency=self.currency)

    def __abs__(self) -> "Money":
        return Money(amount=abs(self.amount), currency=self.currency)

    def __lt__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount <= other.amount

    def __gt__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount > other.amount

    def __ge__(self, other: "Money") -> bool:
        self._assert_same_currency(other)
        return self.amount >= other.amount

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Money):
            return False
        return self.currency == other.currency and self.amount == other.amount

    def round_to(self, decimal_places: int = 2) -> "Money":
        """Round amount using Banker's Rounding (ROUND_HALF_EVEN)."""
        factor = Decimal("10") ** -decimal_places
        rounded_amount = self.amount.quantize(factor, rounding=ROUND_HALF_EVEN)
        return Money(amount=rounded_amount, currency=self.currency)

    @property
    def is_zero(self) -> bool:
        return self.amount == Decimal("0")

    @property
    def is_positive(self) -> bool:
        return self.amount > Decimal("0")

    @property
    def is_negative(self) -> bool:
        return self.amount < Decimal("0")

    def _assert_same_currency(self, other: "Money") -> None:
        if not isinstance(other, Money):
            raise TypeError(f"Operand must be of type Money, got {type(other).__name__}")
        if self.currency != other.currency:
            raise ValueError(
                f"Currency mismatch error: Cannot operate between {self.currency.value} and {other.currency.value}"
            )

    def to_formatted_string(self) -> str:
        symbols = {
            Currency.USD: "$",
            Currency.EUR: "€",
            Currency.GBP: "£",
            Currency.INR: "₹",
            Currency.CAD: "CA$",
            Currency.AUD: "A$",
            Currency.JPY: "¥",
        }
        sym = symbols.get(self.currency, f"{self.currency.value} ")
        return f"{sym}{self.amount:,.2f}"

    def __str__(self) -> str:
        return f"{self.amount} {self.currency.value}"
