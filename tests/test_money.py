from decimal import Decimal, Inexact, ROUND_UP, localcontext

import pytest

from app.money import (
    MAX_MINOR,
    InvalidMoney,
    from_minor_units,
    round_calculation,
    to_minor_units,
)


@pytest.mark.parametrize(
    "value,units",
    [
        ("0.01", 1),
        ("0.10", 10),
        ("0.1000", 10),
        ("1234.56", 123456),
        ("90000000000000.00", MAX_MINOR),
    ],
)
def test_exact_bwp_conversion(value, units):
    assert to_minor_units(Decimal(value), currency="BWP") == units
    assert from_minor_units(units, currency="BWP") == Decimal(value)
    assert from_minor_units(units, currency="BWP").as_tuple().exponent == -2


@pytest.mark.parametrize(
    "value",
    [
        0.1,
        True,
        1,
        "1.00",
        None,
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("-1"),
        Decimal("0"),
        Decimal("-0"),
        Decimal("0.001"),
        Decimal("1.005"),
        Decimal("90000000000000.01"),
        Decimal("1e-10000000"),
    ],
)
def test_invalid_postings_are_never_rounded_or_coerced(value):
    with pytest.raises(InvalidMoney):
        to_minor_units(value, currency="BWP")


@pytest.mark.parametrize("currency", ["", "bwp", "USD", "GBP", None])
def test_currency_must_be_explicit_approved_iso_code(currency):
    with pytest.raises(InvalidMoney):
        to_minor_units(Decimal("1.00"), currency=currency)


@pytest.mark.parametrize("value", [-1, MAX_MINOR + 1, True, 0.5, "1"])
def test_minor_unit_boundary_is_strict(value):
    with pytest.raises(InvalidMoney):
        from_minor_units(value, currency="BWP")


def test_rounding_requires_explicit_authorisation_and_is_not_posting_policy():
    with pytest.raises(PermissionError):
        round_calculation(Decimal("2.345"), currency="BWP")
    assert round_calculation(
        Decimal("2.345"), currency="BWP", authorised=True
    ) == Decimal("2.34")
    assert round_calculation(
        Decimal("2.355"), currency="BWP", authorised=True
    ) == Decimal("2.36")
    with pytest.raises(InvalidMoney):
        to_minor_units(Decimal("2.345"), currency="BWP")


def test_caller_decimal_context_cannot_change_money_policy():
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        context.traps[Inexact] = True
        assert to_minor_units(Decimal("1234.56"), currency="BWP") == 123456
        assert from_minor_units(123456, currency="BWP") == Decimal("1234.56")
        assert round_calculation(
            Decimal("2.345"), currency="BWP", authorised=True
        ) == Decimal("2.34")
