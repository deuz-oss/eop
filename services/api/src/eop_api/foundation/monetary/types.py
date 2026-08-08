from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_PRECISION = Decimal("0.01")


class InvalidMoneyError(Exception):
    """Raised when a `Money` value cannot be constructed from the given amount/currency."""


def _normalize_amount(amount: Decimal | int | float | str | None) -> Decimal:
    if amount is None:
        raise InvalidMoneyError("Money requires an amount")

    if isinstance(amount, float):
        # A float's own binary representation is already an approximation --
        # route it through str() rather than Decimal(float) so normalization
        # below doesn't inherit that imprecision.
        amount = str(amount)

    try:
        decimal_amount = Decimal(amount)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidMoneyError(f"Invalid monetary amount: {amount!r}") from exc

    if not decimal_amount.is_finite():
        raise InvalidMoneyError(f"Invalid monetary amount: {amount!r}")

    return decimal_amount.quantize(_PRECISION, rounding=ROUND_HALF_UP)


def _normalize_currency(currency: str | None) -> str:
    if currency is None or not isinstance(currency, str):
        raise InvalidMoneyError("Money requires a currency")

    stripped = currency.strip()
    if not stripped:
        raise InvalidMoneyError("Money requires a non-empty currency")

    return stripped


@dataclass(frozen=True)
class Money:
    """Immutable, currency-scoped monetary value.

    Represents a monetary amount and its currency context only -- it owns
    no business meaning, lifecycle, or persistence, and knows nothing about
    Compensation, Payroll, Payslip, Employee, Organization, or accounting
    concepts.

    Every amount is normalized to the approved system precision (2 decimal
    places, half-up) at construction, so two `Money` values are equal
    whenever they represent the same normalized amount and currency,
    regardless of how the amount was originally supplied.
    """

    amount: Decimal
    currency: str

    def __init__(self, amount: Decimal | int | float | str, currency: str) -> None:
        object.__setattr__(self, "amount", _normalize_amount(amount))
        object.__setattr__(self, "currency", _normalize_currency(currency))

    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
