"""Pure, non-postable BWP_TOURNAMENT_V1 scenarios; never touch an account."""

from dataclasses import dataclass
from fractions import Fraction
from app.money import MAX_MINOR, InvalidMoney, require_currency

VERSION = "BWP_TOURNAMENT_V1"
WEIGHTS = (60, 30, 10)


@dataclass(frozen=True)
class PreviewWinner:
    player_id: int
    position: int


@dataclass(frozen=True)
class PrizeShare:
    player_id: int
    position: int
    amount_minor: int


@dataclass(frozen=True)
class PrizePreview:
    policy_version: str
    currency: str
    hypothetical_distributable_minor: int
    shares: tuple[PrizeShare, ...]
    postable: bool = False
    token_state: str = "UNRESOLVED"


def minor(value, *, positive=False):
    if type(value) is not int or not (1 if positive else 0) <= value <= MAX_MINOR:
        raise InvalidMoney("Exact bounded integer thebe required")
    return value


def allocate_preview(
    amount_minor: int, winners: tuple[PreviewWinner, ...], *, currency: str
) -> PrizePreview:
    require_currency(currency)
    minor(amount_minor)
    ordered = tuple(sorted(winners, key=lambda w: w.position))
    if not 1 <= len(ordered) <= 3 or any(
        type(w.player_id) is not int or w.player_id <= 0 or type(w.position) is not int
        for w in ordered
    ):
        raise ValueError("One to three eligible winners required")
    if len({w.player_id for w in ordered}) != len(ordered) or [
        w.position for w in ordered
    ] != list(range(1, len(ordered) + 1)):
        raise ValueError("Unique winners and consecutive finishing positions required")
    weights = WEIGHTS[: len(ordered)]
    denominator = sum(weights)
    floors = [amount_minor * weight // denominator for weight in weights]
    remainders = [
        Fraction(amount_minor * weight, denominator) - floor
        for weight, floor in zip(weights, floors)
    ]
    for index in sorted(
        range(len(ordered)), key=lambda i: (-remainders[i], ordered[i].position)
    )[: amount_minor - sum(floors)]:
        floors[index] += 1
    return PrizePreview(
        VERSION,
        currency,
        amount_minor,
        tuple(
            PrizeShare(w.player_id, w.position, value)
            for w, value in zip(ordered, floors)
        ),
    )


@dataclass(frozen=True)
class TokenBasisPreview:
    hypothetical_gross_minor: int
    unresolved_deduction_basis: Fraction
    hypothetical_distributable: Fraction
    prize_preview: PrizePreview | None
    token_asset: None = None
    token_units: None = None
    actual_deduction_minor: None = None
    postable: bool = False
    token_state: str = "UNRESOLVED"


def preview_token_basis(
    gross_minor: int, winners: tuple[PreviewWinner, ...], *, currency: str
) -> TokenBasisPreview:
    require_currency(currency)
    minor(gross_minor)
    allocate_preview(0, winners, currency=currency)
    basis = Fraction(gross_minor, 10)
    distributable = Fraction(gross_minor) - basis
    # No token rounding policy is chosen, even in a scenario.
    preview = (
        allocate_preview(distributable.numerator, winners, currency=currency)
        if distributable.denominator == 1
        else None
    )
    return TokenBasisPreview(gross_minor, basis, distributable, preview)
