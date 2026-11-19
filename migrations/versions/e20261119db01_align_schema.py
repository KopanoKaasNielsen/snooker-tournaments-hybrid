"""align historical schema with application models

Revision ID: e20261119db01
Revises: d27f9a18494f
Create Date: 2026-11-19 16:23:03.900976

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e20261119db01"
down_revision: Union[str, None] = "d27f9a18494f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _require_empty() -> None:
    # Historical migrations omitted financial fields and enum semantics changed.
    # Never infer balances, timestamps or type conversions for historical records.
    for table in (
        "players",
        "tournaments",
        "matches",
        "tournament_registrations",
        "tournament_results",
    ):
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError(
                "Populated historical schema requires an explicitly reviewed data migration; "
                "no balances or records have been inferred."
            )


def upgrade() -> None:
    _require_empty()
    op.create_table(
        "wallet_transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("player_id", sa.Integer(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("deposit", "withdrawal", "prize", "fee", name="transactiontype"),
            nullable=False,
        ),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name=op.f("fk_wallet_transactions_player_id_players"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_wallet_transactions")),
    )
    with op.batch_alter_table("wallet_transactions", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_wallet_transactions_id"), ["id"], unique=False
        )

    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.alter_column(
            "tournament_id", existing_type=sa.INTEGER(), nullable=False
        )
        batch_op.alter_column(
            "scheduled_at", existing_type=sa.DATETIME(), nullable=False
        )
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=False)

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.add_column(sa.Column("elo", sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column("balance", sa.Float(), nullable=False))
        batch_op.alter_column("rating", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=False)

    with op.batch_alter_table("tournament_registrations", schema=None) as batch_op:
        batch_op.alter_column(
            "tournament_id", existing_type=sa.INTEGER(), nullable=False
        )
        batch_op.alter_column("player_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("paid", existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.alter_column("waived", existing_type=sa.BOOLEAN(), nullable=False)
        batch_op.alter_column(
            "contribution", existing_type=sa.INTEGER(), nullable=False
        )
        batch_op.create_unique_constraint(
            "uq_registration", ["tournament_id", "player_id"]
        )

    with op.batch_alter_table("tournament_results", schema=None) as batch_op:
        batch_op.alter_column(
            "tournament_id", existing_type=sa.INTEGER(), nullable=False
        )
        batch_op.alter_column("player_id", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=False)
        batch_op.create_unique_constraint(
            "uq_tournament_position", ["tournament_id", "position"]
        )

    with op.batch_alter_table("tournaments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("created_at", sa.DateTime(), nullable=False))
        batch_op.alter_column("date", existing_type=sa.DATETIME(), nullable=False)
        batch_op.alter_column(
            "type",
            existing_type=sa.VARCHAR(length=11),
            type_=sa.Enum(
                "league", "knockout", "double_elimination", name="tournamenttype"
            ),
            nullable=False,
        )
        batch_op.alter_column(
            "status", existing_type=sa.VARCHAR(length=9), nullable=False
        )
        batch_op.alter_column("best_of", existing_type=sa.INTEGER(), nullable=False)
        batch_op.alter_column("entry_fee", existing_type=sa.INTEGER(), nullable=False)


def downgrade() -> None:
    _require_empty()
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM wallet_transactions LIMIT 1"))
        .first()
    ):
        raise RuntimeError("Cannot downgrade a populated wallet ledger")
    with op.batch_alter_table("tournaments", schema=None) as batch_op:
        batch_op.alter_column("entry_fee", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column("best_of", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column(
            "status", existing_type=sa.VARCHAR(length=9), nullable=True
        )
        batch_op.alter_column(
            "type",
            existing_type=sa.Enum(
                "league", "knockout", "double_elimination", name="tournamenttype"
            ),
            type_=sa.VARCHAR(length=11),
            nullable=True,
        )
        batch_op.alter_column("date", existing_type=sa.DATETIME(), nullable=True)
        batch_op.drop_column("created_at")

    with op.batch_alter_table("tournament_results", schema=None) as batch_op:
        batch_op.drop_constraint("uq_tournament_position", type_="unique")
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=True)
        batch_op.alter_column("player_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column(
            "tournament_id", existing_type=sa.INTEGER(), nullable=True
        )

    with op.batch_alter_table("tournament_registrations", schema=None) as batch_op:
        batch_op.drop_constraint("uq_registration", type_="unique")
        batch_op.alter_column("contribution", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column("waived", existing_type=sa.BOOLEAN(), nullable=True)
        batch_op.alter_column("paid", existing_type=sa.BOOLEAN(), nullable=True)
        batch_op.alter_column("player_id", existing_type=sa.INTEGER(), nullable=True)
        batch_op.alter_column(
            "tournament_id", existing_type=sa.INTEGER(), nullable=True
        )

    with op.batch_alter_table("players", schema=None) as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=True)
        batch_op.alter_column("rating", existing_type=sa.INTEGER(), nullable=True)
        batch_op.drop_column("balance")
        batch_op.drop_column("elo")

    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.alter_column("created_at", existing_type=sa.DATETIME(), nullable=True)
        batch_op.alter_column(
            "scheduled_at", existing_type=sa.DATETIME(), nullable=True
        )
        batch_op.alter_column(
            "tournament_id", existing_type=sa.INTEGER(), nullable=True
        )

    with op.batch_alter_table("wallet_transactions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_wallet_transactions_id"))

    op.drop_table("wallet_transactions")
