"""Internal BWP subledger, not connected to any HTTP financial mutation."""

from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Context, Decimal, localcontext
from pathlib import Path
from uuid import UUID, uuid4
from urllib.parse import unquote, urlsplit

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.financial_schema import ledger_triggers_match
from app.models import FinancialLedgerEntry, FinancialWallet, Player, WalletTransaction
from app.money import MAX_MINOR, from_minor_units, require_currency, to_minor_units

CREDITS = {"deposit", "prize"}
DEBITS = {"withdrawal", "fee"}


class FinancialError(ValueError):
    pass


class InsufficientFunds(FinancialError):
    pass


class IdempotencyConflict(FinancialError):
    pass


class LegacyAdoptionRequired(FinancialError):
    pass


class FinancialBusy(FinancialError):
    """Retry the whole unit with the same idempotency key after lock contention."""


@dataclass(frozen=True)
class Receipt:
    id: str
    idempotency_key: str
    wallet_id: str
    currency: str
    kind: str
    amount: Decimal
    balance_before: Decimal
    balance_after: Decimal
    sequence: int


@dataclass(frozen=True)
class WalletSnapshot:
    id: str
    player_id: int
    currency: str
    balance: Decimal
    sequence: int


@dataclass(frozen=True)
class Reconciliation:
    wallet_id: str
    currency: str
    balance: Decimal
    ledger_balance: Decimal
    entry_count: int
    issues: tuple[str, ...]

    @property
    def consistent(self) -> bool:
        return not self.issues


def _receipt(entry: FinancialLedgerEntry) -> Receipt:
    return Receipt(
        entry.id,
        entry.idempotency_key,
        entry.wallet_id,
        entry.currency,
        entry.kind,
        from_minor_units(entry.amount_minor, currency=entry.currency),
        from_minor_units(entry.balance_before_minor, currency=entry.currency),
        from_minor_units(entry.balance_after_minor, currency=entry.currency),
        entry.sequence,
    )


def _key(key: str) -> None:
    try:
        parsed = UUID(key) if isinstance(key, str) and len(key) == 36 else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.version != 4 or str(parsed) != key:
        raise FinancialError("A canonical UUID4 idempotency key is required")


def legacy_is_pristine(db, player_id: int) -> bool:
    player = db.get(Player, player_id, populate_existing=True)
    if player is None:
        raise FinancialError("Player not found")
    return (
        player.balance == 0
        and db.scalar(
            select(WalletTransaction.id)
            .where(WalletTransaction.player_id == player_id)
            .limit(1)
        )
        is None
    )


class FinancialWalletService:
    """Own fresh sessions and one SQLite transaction per call; never commit caller work."""

    def __init__(self, engine: Engine):
        if engine.dialect.name != "sqlite":
            raise FinancialError(
                "Financial foundation supports SQLite only; PostgreSQL locking is not implemented"
            )
        self.engine = engine
        self._sessions = sessionmaker(bind=engine, autoflush=False)

    @contextmanager
    def _transaction(self, *, write: bool):
        if write and self.engine.url.database:
            protected = Path(__file__).resolve().parents[2] / "snooker.db"
            database = self.engine.url.database
            if database.startswith("file:"):
                database = unquote(urlsplit(database).path)
            if Path(database).resolve() == protected:
                raise FinancialError(
                    "Financial writes refuse the preserved repository database"
                )
        try:
            with self._sessions() as db, db.begin():
                # Begin before ANY reads, including idempotency checks. No stale read snapshot
                # can precede acquiring SQLite's single-writer reservation.
                db.connection().exec_driver_sql("BEGIN IMMEDIATE" if write else "BEGIN")
                if not ledger_triggers_match(db.connection()):
                    raise FinancialError(
                        "Exact-money integrity triggers are missing or changed; verify migrations"
                    )
                yield db
        except OperationalError as exc:
            if "locked" in str(exc.orig).lower() or "busy" in str(exc.orig).lower():
                raise FinancialBusy(
                    "SQLite is busy; retry using the same idempotency key"
                ) from None
            raise

    def open_wallet(self, player_id: int, *, currency: str) -> WalletSnapshot:
        require_currency(currency)
        with self._transaction(write=True) as db:
            if not legacy_is_pristine(db, player_id):
                raise LegacyAdoptionRequired(
                    "Existing money requires separately approved reconciliation/adoption"
                )
            wallet = db.scalar(
                select(FinancialWallet).where(FinancialWallet.player_id == player_id)
            )
            if wallet is None:
                wallet = FinancialWallet(
                    id=str(uuid4()), player_id=player_id, currency=currency
                )
                db.add(wallet)
                db.flush()
            result = WalletSnapshot(
                wallet.id,
                wallet.player_id,
                wallet.currency,
                from_minor_units(wallet.balance_minor, currency=wallet.currency),
                wallet.sequence,
            )
        return result

    def post(
        self,
        wallet_id: str,
        *,
        kind: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
    ) -> Receipt:
        units = to_minor_units(amount, currency=currency)
        _key(idempotency_key)
        if not isinstance(kind, str) or kind not in CREDITS | DEBITS:
            raise FinancialError("Invalid posting kind")
        with self._transaction(write=True) as db:
            return self._post_in_session(
                db,
                wallet_id,
                kind=kind,
                amount=amount,
                currency=currency,
                idempotency_key=idempotency_key,
            )

    def _post_in_session(
        self,
        db,
        wallet_id: str,
        *,
        kind: str,
        amount: Decimal,
        currency: str,
        idempotency_key: str,
        _operation_id: str | None = None,
    ) -> Receipt:
        """Private participant: caller MUST own this service's existing transaction; no commit."""
        from sqlalchemy import inspect
        from app.models import FinancialOperation

        units = to_minor_units(amount, currency=currency)
        _key(idempotency_key)
        if not isinstance(kind, str) or kind not in CREDITS | DEBITS:
            raise FinancialError("Invalid posting kind")
        if db.get_bind() is not self.engine or not db.in_transaction():
            raise FinancialError("Posting participant requires the owning transaction")
        if inspect(db.connection()).has_table("financial_operations"):
            reserved = db.scalar(
                select(FinancialOperation).where(
                    (FinancialOperation.id == idempotency_key)
                    | (FinancialOperation.idempotency_key == idempotency_key)
                )
            )
            if reserved is not None and (
                _operation_id != reserved.id
                or idempotency_key != reserved.id
                or reserved.status != "VERIFIED"
                or reserved.wallet_id != wallet_id
                or reserved.amount_minor != units
                or reserved.currency != currency
                or reserved.kind != kind
            ):
                raise FinancialError(
                    "Operation-managed key requires its coordinated posting workflow"
                )
            if _operation_id is not None and reserved is None:
                raise FinancialError("Coordinated operation not found")
        previous = db.scalar(
            select(FinancialLedgerEntry).where(
                FinancialLedgerEntry.idempotency_key == idempotency_key
            )
        )
        if previous is not None:
            if (
                previous.wallet_id,
                previous.currency,
                previous.kind,
                previous.amount_minor,
            ) != (wallet_id, currency, kind, units):
                raise IdempotencyConflict(
                    "Idempotency key belongs to a different posting payload"
                )
            return _receipt(previous)
        wallet = db.get(FinancialWallet, wallet_id)
        if wallet is None:
            raise FinancialError("Wallet not found")
        if wallet.currency != currency:
            raise FinancialError("Wallet currency mismatch")
        if not legacy_is_pristine(db, wallet.player_id):
            raise LegacyAdoptionRequired(
                "Legacy activity detected; no currency or balance conversion is authorised"
            )
        delta = units if kind in CREDITS else -units
        row = db.execute(
            update(FinancialWallet)
            .where(
                FinancialWallet.id == wallet_id,
                FinancialWallet.balance_minor + delta >= 0,
                FinancialWallet.balance_minor + delta <= MAX_MINOR,
                FinancialWallet.sequence < MAX_MINOR,
            )
            .values(
                balance_minor=FinancialWallet.balance_minor + delta,
                sequence=FinancialWallet.sequence + 1,
            )
            .returning(FinancialWallet.balance_minor, FinancialWallet.sequence)
        ).first()
        if row is None:
            if kind in DEBITS:
                raise InsufficientFunds("Insufficient balance")
            raise FinancialError("Wallet balance or sequence limit exceeded")
        after, sequence = row
        entry = FinancialLedgerEntry(
            id=str(uuid4()),
            idempotency_key=idempotency_key,
            wallet_id=wallet_id,
            currency=currency,
            kind=kind,
            amount_minor=units,
            balance_before_minor=after - delta,
            balance_after_minor=after,
            sequence=sequence,
        )
        db.add(entry)
        db.flush()  # DB constraints, chain checks and uniqueness precede commit.
        result = _receipt(entry)
        return result

    def reconcile(self) -> tuple[Reconciliation, ...]:
        """One consistent read-only snapshot; report, never auto-repair discrepancies."""
        reports = []
        with (
            self._transaction(write=False) as db,
            localcontext(Context(prec=50)) as context,
        ):
            context.prec = 50
            wallets = db.scalars(
                select(FinancialWallet).order_by(FinancialWallet.id)
            ).all()
            for wallet in wallets:
                entries = db.scalars(
                    select(FinancialLedgerEntry)
                    .where(FinancialLedgerEntry.wallet_id == wallet.id)
                    .order_by(FinancialLedgerEntry.sequence)
                ).all()
                issues = []
                previous = Decimal(0)
                total = Decimal(0)
                for expected, entry in enumerate(entries, 1):
                    before = from_minor_units(
                        entry.balance_before_minor, currency=entry.currency
                    )
                    after = from_minor_units(
                        entry.balance_after_minor, currency=entry.currency
                    )
                    amount = from_minor_units(
                        entry.amount_minor, currency=entry.currency
                    )
                    signed = amount if entry.kind in CREDITS else -amount
                    if entry.sequence != expected or before != previous:
                        issues.append("ledger_chain_discontinuity")
                    if after != before + signed or entry.currency != wallet.currency:
                        issues.append("invalid_ledger_arithmetic_or_currency")
                    total += signed
                    previous = after
                balance = from_minor_units(
                    wallet.balance_minor, currency=wallet.currency
                )
                if balance != total or balance != previous:
                    issues.append("balance_ledger_mismatch")
                if wallet.sequence != len(entries):
                    issues.append("wallet_sequence_mismatch")
                if not legacy_is_pristine(db, wallet.player_id):
                    issues.append("legacy_activity_requires_review")
                reports.append(
                    Reconciliation(
                        wallet.id,
                        wallet.currency,
                        balance,
                        total,
                        len(entries),
                        tuple(dict.fromkeys(issues)),
                    )
                )
        return tuple(reports)
