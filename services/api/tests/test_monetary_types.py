from decimal import Decimal

import pytest

from eop_api.foundation.monetary.types import InvalidMoneyError, Money


def test_construction_from_int_and_str_are_equal():
    assert Money(1000, "IDR") == Money("1000", "IDR")


def test_construction_normalizes_to_two_decimal_places():
    assert str(Money(1000, "IDR").amount) == "1000.00"


def test_missing_amount_rejected():
    with pytest.raises(InvalidMoneyError):
        Money(None, "IDR")  # type: ignore[arg-type]


def test_missing_currency_rejected():
    with pytest.raises(InvalidMoneyError):
        Money(1000, None)  # type: ignore[arg-type]


def test_empty_currency_rejected():
    with pytest.raises(InvalidMoneyError):
        Money(1000, "")


def test_whitespace_only_currency_rejected():
    with pytest.raises(InvalidMoneyError):
        Money(1000, "   ")


def test_invalid_numeric_amount_rejected():
    with pytest.raises(InvalidMoneyError):
        Money("not-a-number", "IDR")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.125", "10.13"),
        ("10.124", "10.12"),
        ("10.115", "10.12"),
        ("0.005", "0.01"),
    ],
)
def test_precision_normalizes_with_half_up_rounding(raw: str, expected: str):
    assert str(Money(raw, "IDR").amount) == expected


def test_equal_when_same_amount_and_currency():
    assert Money(100, "IDR") == Money(100.00, "IDR")


def test_not_equal_when_currency_differs():
    assert Money(100, "IDR") != Money(100, "USD")


def test_string_representation():
    assert str(Money(1000, "IDR")) == "1000.00 IDR"


def test_money_is_immutable():
    money = Money(100, "IDR")

    with pytest.raises(AttributeError):
        money.amount = Decimal("200.00")  # type: ignore[misc]
