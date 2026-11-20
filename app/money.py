"""Approved new-money policy: BWP, 100 thebe/pula, no binary float arithmetic."""

from decimal import (
    Context,
    Decimal,
    DecimalException,
    Inexact,
    ROUND_HALF_EVEN,
    localcontext,
)

CURRENCY = "BWP"
QUANTUM = Decimal("0.01")
MAX_MINOR = 9_000_000_000_000_000
MAX_MAJOR = Decimal("90000000000000.00")


class InvalidMoney(ValueError):
    pass


def require_currency(currency: str) -> None:
    if currency != CURRENCY:
        raise InvalidMoney("An explicit ISO 4217 BWP currency is required")


def _decimal(value: Decimal, currency: str) -> None:
    require_currency(currency)
    if not isinstance(value, Decimal) or not value.is_finite():
        raise InvalidMoney("Money must be a finite Decimal, never float/bool/string")
    if value < 0 or value > MAX_MAJOR:
        raise InvalidMoney("Money is outside the supported range")


def to_minor_units(value: Decimal, *, currency: str) -> int:
    """Validate a positive posting exactly; do not round sub-thebe values."""
    _decimal(value, currency)
    if value == 0:
        raise InvalidMoney("Posting amount must be positive")
    try:
        with localcontext(Context(prec=50)) as context:
            context.prec = 50
            context.traps[Inexact] = True
            units = (value * Decimal(100)).to_integral_exact()
            if not 1 <= units <= MAX_MINOR:
                raise InvalidMoney("Posting amount is outside the supported range")
            return int(units)
    except DecimalException:
        raise InvalidMoney(
            "Posting must be exact to one thebe; no rounding allowed"
        ) from None


def from_minor_units(value: int, *, currency: str) -> Decimal:
    require_currency(currency)
    if type(value) is not int or not 0 <= value <= MAX_MINOR:
        raise InvalidMoney("Invalid integer minor units")
    with localcontext(Context(prec=50)) as context:
        context.prec = 50
        return Decimal(value).scaleb(-2).quantize(QUANTUM)


def round_calculation(
    value: Decimal, *, currency: str, authorised: bool = False
) -> Decimal:
    """Explicit opt-in calculation helper; never used by postings or legacy prizes."""
    if authorised is not True:
        raise PermissionError("Calculation rounding requires explicit authorisation")
    _decimal(value, currency)
    with localcontext(Context(prec=50)) as context:
        context.prec = 50
        context.traps[Inexact] = False
        return value.quantize(QUANTUM, rounding=ROUND_HALF_EVEN)
