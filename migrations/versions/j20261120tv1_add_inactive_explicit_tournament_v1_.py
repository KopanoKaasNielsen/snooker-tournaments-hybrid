"""add inactive explicit tournament V1 policy

Revision ID: j20261120tv1
Revises: i20261120tfin
Create Date: 2026-11-20 16:38:40.724042

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "j20261120tv1"
down_revision: Union[str, None] = "i20261120tfin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "sqlite":
        raise RuntimeError("Inactive V1 financial policy currently requires SQLite")
    # Additive only: no existing rows are assigned or converted.
    op.create_table(
        "tournament_v1_policies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("tournament_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("registration_deadline", sa.DateTime(), nullable=False),
        sa.Column("commences_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("activation_state", sa.String(length=16), nullable=False),
        sa.Column("token_state", sa.String(length=16), nullable=False),
        sa.Column("token_direction", sa.String(length=32), nullable=False),
        sa.Column("first_weight", sa.Integer(), nullable=False),
        sa.Column("second_weight", sa.Integer(), nullable=False),
        sa.Column("third_weight", sa.Integer(), nullable=False),
        sa.Column("token_numerator", sa.Integer(), nullable=False),
        sa.Column("token_denominator", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "activation_state='INACTIVE' AND token_state='UNRESOLVED' AND token_direction='DEDUCT_BEFORE_PRIZES'",
            name=op.f("ck_tournament_v1_policies_activation_blocked"),
        ),
        sa.CheckConstraint(
            "typeof(capacity)='integer' AND capacity>0",
            name=op.f("ck_tournament_v1_policies_positive_capacity"),
        ),
        sa.CheckConstraint(
            "typeof(price_minor)='integer' AND price_minor BETWEEN 0 AND 9000000000000000",
            name=op.f("ck_tournament_v1_policies_price_range"),
        ),
        sa.CheckConstraint(
            "version='BWP_TOURNAMENT_V1' AND currency='BWP'",
            name=op.f("ck_tournament_v1_policies_version_currency"),
        ),
        sa.CheckConstraint(
            "first_weight=60 AND second_weight=30 AND third_weight=10 AND token_numerator=1 AND token_denominator=10",
            name=op.f("ck_tournament_v1_policies_approved_weights"),
        ),
        sa.CheckConstraint(
            "registration_deadline<=commences_at AND created_at<registration_deadline",
            name=op.f("ck_tournament_v1_policies_policy_dates"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_tournament_v1_policies_created_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["tournament_id"],
            ["tournaments.id"],
            name=op.f("fk_tournament_v1_policies_tournament_id_tournaments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tournament_v1_policies")),
        sa.UniqueConstraint(
            "tournament_id", name=op.f("uq_tournament_v1_policies_tournament_id")
        ),
    )
    op.create_table(
        "tournament_pool_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("policy_id", sa.String(length=36), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("cleared_minor", sa.BigInteger(), nullable=False),
        sa.Column("spendable_minor", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "currency='BWP' AND state='NON_SPENDABLE' AND cleared_minor=0 AND spendable_minor=0",
            name=op.f("ck_tournament_pool_accounts_no_pool_money"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["tournament_v1_policies.id"],
            name=op.f("fk_tournament_pool_accounts_policy_id_tournament_v1_policies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tournament_pool_accounts")),
        sa.UniqueConstraint(
            "policy_id", name=op.f("uq_tournament_pool_accounts_policy_id")
        ),
    )
    op.create_table(
        "tournament_v1_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("policy_id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("identity_key", sa.String(length=100), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("pool_id", sa.String(length=36), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("player_id", sa.Integer(), nullable=True),
        sa.Column("registration_id", sa.Integer(), nullable=True),
        sa.Column("match_id", sa.Integer(), nullable=True),
        sa.Column("amount_minor", sa.BigInteger(), nullable=True),
        sa.Column("operation_id", sa.String(length=36), nullable=True),
        sa.Column("receipt_id", sa.String(length=36), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("data_json", sa.String(), nullable=False),
        sa.Column("financially_effective", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(kind IN ('FEE_OBLIGATION','FEE_REFERENCE','REFUND_REVIEW') AND amount_minor IS NOT NULL) OR (kind NOT IN ('FEE_OBLIGATION','FEE_REFERENCE','REFUND_REVIEW') AND amount_minor IS NULL)",
            name=op.f("ck_tournament_v1_records_amount_scope"),
        ),
        sa.CheckConstraint(
            "(kind='FEE_REFERENCE' AND operation_id IS NOT NULL AND receipt_id IS NOT NULL) OR (kind!='FEE_REFERENCE' AND operation_id IS NULL AND receipt_id IS NULL)",
            name=op.f("ck_tournament_v1_records_receipt_scope"),
        ),
        sa.CheckConstraint(
            "amount_minor IS NULL OR (typeof(amount_minor)='integer' AND amount_minor BETWEEN 0 AND 9000000000000000)",
            name=op.f("ck_tournament_v1_records_fact_amount"),
        ),
        sa.CheckConstraint(
            "kind IN ('ELIGIBILITY','REGISTRATION','FEE_OBLIGATION','CONFIRMATION','WAIVER','FEE_REFERENCE','SPONSOR_REVIEW','CANCELLATION','REFUND_REVIEW','MATCH_RESULT','RESULTS_REVISION','RESULTS_APPROVAL','PAYOUT_SCHEDULE')",
            name=op.f("ck_tournament_v1_records_fact_kind"),
        ),
        sa.CheckConstraint(
            "financially_effective=0",
            name=op.f("ck_tournament_v1_records_no_financial_effect"),
        ),
        sa.CheckConstraint(
            "json_valid(data_json)",
            name=op.f("ck_tournament_v1_records_valid_snapshot"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_tournament_v1_records_created_by_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["match_id"],
            ["matches.id"],
            name=op.f("fk_tournament_v1_records_match_id_matches"),
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["financial_operations.id"],
            name=op.f("fk_tournament_v1_records_operation_id_financial_operations"),
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["users.id"],
            name=op.f("fk_tournament_v1_records_owner_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["tournament_v1_records.id"],
            name=op.f("fk_tournament_v1_records_parent_id_tournament_v1_records"),
        ),
        sa.ForeignKeyConstraint(
            ["player_id"],
            ["players.id"],
            name=op.f("fk_tournament_v1_records_player_id_players"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["tournament_v1_policies.id"],
            name=op.f("fk_tournament_v1_records_policy_id_tournament_v1_policies"),
        ),
        sa.ForeignKeyConstraint(
            ["pool_id"],
            ["tournament_pool_accounts.id"],
            name=op.f("fk_tournament_v1_records_pool_id_tournament_pool_accounts"),
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["financial_ledger_entries.id"],
            name=op.f("fk_tournament_v1_records_receipt_id_financial_ledger_entries"),
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["tournament_registrations.id"],
            name=op.f(
                "fk_tournament_v1_records_registration_id_tournament_registrations"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tournament_v1_records")),
        sa.UniqueConstraint(
            "operation_id", name=op.f("uq_tournament_v1_records_operation_id")
        ),
        sa.UniqueConstraint(
            "policy_id", "kind", "identity_key", name="uq_v1_fact_identity"
        ),
        sa.UniqueConstraint(
            "receipt_id", name=op.f("uq_tournament_v1_records_receipt_id")
        ),
    )
    with op.batch_alter_table("tournament_v1_records", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_tournament_v1_records_parent_id"),
            ["parent_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_tournament_v1_records_policy_id"),
            ["policy_id"],
            unique=False,
        )

    op.create_table(
        "tournament_v1_requests",
        sa.Column("idempotency_key", sa.String(length=36), nullable=False),
        sa.Column("policy_id", sa.String(length=36), nullable=False),
        sa.Column("record_id", sa.String(length=36), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(idempotency_key) = 36 AND substr(idempotency_key,9,1)='-' AND substr(idempotency_key,14,1)='-' AND substr(idempotency_key,19,1)='-' AND substr(idempotency_key,24,1)='-' AND substr(idempotency_key,15,1)='4' AND substr(idempotency_key,20,1) IN ('8','9','a','b') AND length(replace(idempotency_key,'-',''))=32 AND replace(idempotency_key,'-','') NOT GLOB '*[^0-9a-f]*'",
            name=op.f("ck_tournament_v1_requests_v1_request_uuid"),
        ),
        sa.CheckConstraint(
            "length(payload_digest)=64 AND payload_digest NOT GLOB '*[^0-9a-f]*'",
            name=op.f("ck_tournament_v1_requests_v1_payload_digest"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=op.f("fk_tournament_v1_requests_actor_id_users"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["tournament_v1_policies.id"],
            name=op.f("fk_tournament_v1_requests_policy_id_tournament_v1_policies"),
        ),
        sa.ForeignKeyConstraint(
            ["record_id"],
            ["tournament_v1_records.id"],
            name=op.f("fk_tournament_v1_requests_record_id_tournament_v1_records"),
        ),
        sa.PrimaryKeyConstraint(
            "idempotency_key", name=op.f("pk_tournament_v1_requests")
        ),
    )
    with op.batch_alter_table("tournament_v1_requests", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_tournament_v1_requests_policy_id"),
            ["policy_id"],
            unique=False,
        )

    # ### end Alembic commands ###

    op.execute(
        "CREATE TRIGGER tournament_v1_policies_update_blocked BEFORE UPDATE ON tournament_v1_policies BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER tournament_v1_policies_delete_blocked BEFORE DELETE ON tournament_v1_policies BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER tournament_pool_accounts_update_blocked BEFORE UPDATE ON tournament_pool_accounts BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER tournament_pool_accounts_delete_blocked BEFORE DELETE ON tournament_pool_accounts BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER tournament_v1_records_update_blocked BEFORE UPDATE ON tournament_v1_records BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER tournament_v1_records_delete_blocked BEFORE DELETE ON tournament_v1_records BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER tournament_v1_requests_update_blocked BEFORE UPDATE ON tournament_v1_requests BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER tournament_v1_requests_delete_blocked BEFORE DELETE ON tournament_v1_requests BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
    )
    op.execute(
        "CREATE TRIGGER v1_policy_new_only BEFORE INSERT ON tournament_v1_policies\nBEGIN\n SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM tournaments t JOIN users u ON u.id=NEW.created_by_id\n  WHERE t.id=NEW.tournament_id AND t.created_at=NEW.created_at AND t.status='PENDING' AND t.entry_fee=0\n   AND u.is_active=1 AND u.role IN ('organiser','administrator'))\n  OR EXISTS(SELECT 1 FROM tournament_registrations r WHERE r.tournament_id=NEW.tournament_id)\n  OR EXISTS(SELECT 1 FROM matches m WHERE m.tournament_id=NEW.tournament_id)\n  OR EXISTS(SELECT 1 FROM tournament_results r WHERE r.tournament_id=NEW.tournament_id)\n THEN RAISE(ABORT,'Explicit newly created tournament policy required') END;\nEND"
    )
    op.execute(
        "CREATE TRIGGER v1_record_scope BEFORE INSERT ON tournament_v1_records\nBEGIN\n SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.created_by_id AND u.is_active=1)\n THEN RAISE(ABORT,'Active V1 actor required') END;\n SELECT CASE WHEN NEW.kind IN ('ELIGIBILITY','MATCH_RESULT','RESULTS_REVISION','CANCELLATION','PAYOUT_SCHEDULE') AND NOT EXISTS(\n  SELECT 1 FROM users u JOIN tournament_v1_policies p ON p.id=NEW.policy_id WHERE u.id=NEW.created_by_id AND u.is_active=1\n   AND (u.role='administrator' OR (u.role='organiser' AND EXISTS(SELECT 1 FROM tournament_organisers a WHERE a.user_id=u.id AND a.tournament_id=p.tournament_id)))\n ) THEN RAISE(ABORT,'Assigned V1 authority required') END;\n SELECT CASE WHEN NEW.kind IN ('FEE_OBLIGATION','CONFIRMATION','WAIVER','FEE_REFERENCE','RESULTS_APPROVAL','PAYOUT_SCHEDULE') AND (\n   NEW.parent_id IS NULL OR NEW.identity_key IS NOT NEW.parent_id OR EXISTS(SELECT 1 FROM tournament_v1_records x WHERE x.policy_id=NEW.policy_id AND x.kind=NEW.kind AND x.parent_id=NEW.parent_id))\n THEN RAISE(ABORT,'Unique immutable parent identity required') END;\n SELECT CASE WHEN NEW.kind IN ('REGISTRATION','ELIGIBILITY') AND NEW.identity_key IS NOT CAST(NEW.owner_id AS TEXT)\n THEN RAISE(ABORT,'Unique owner identity required') END;\n SELECT CASE WHEN NEW.kind IN ('CONFIRMATION','WAIVER') AND NOT EXISTS(SELECT 1 FROM tournament_v1_records r WHERE r.id=NEW.parent_id AND r.kind='REGISTRATION' AND r.owner_id=NEW.owner_id AND r.player_id=NEW.player_id)\n THEN RAISE(ABORT,'Confirmation/waiver registration scope mismatch') END;\n SELECT CASE WHEN NEW.kind='FEE_REFERENCE' AND (NEW.amount_minor<=0 OR json_extract(NEW.data_json,'$.cleared') IS NOT 0)\n THEN RAISE(ABORT,'Fee reference cannot imply clearing') END;\n SELECT CASE WHEN NEW.kind='REFUND_REVIEW' AND json_extract(NEW.data_json,'$.refunded_minor') IS NOT 0\n THEN RAISE(ABORT,'Refund reviews cannot imply money movement') END;\n SELECT CASE WHEN NEW.match_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM matches m JOIN tournament_v1_policies p ON p.id=NEW.policy_id WHERE m.id=NEW.match_id AND m.tournament_id=p.tournament_id)\n THEN RAISE(ABORT,'V1 match scope mismatch') END;\n SELECT CASE WHEN NEW.kind='ELIGIBILITY' AND NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.owner_id AND u.is_active=1 AND u.player_id=NEW.player_id AND u.id!=NEW.created_by_id)\n THEN RAISE(ABORT,'Independent eligibility review required') END;\n SELECT CASE WHEN NEW.parent_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM tournament_v1_records p WHERE p.id=NEW.parent_id AND p.policy_id=NEW.policy_id)\n THEN RAISE(ABORT,'V1 parent scope mismatch') END;\n SELECT CASE WHEN NEW.pool_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM tournament_pool_accounts p WHERE p.id=NEW.pool_id AND p.policy_id=NEW.policy_id)\n THEN RAISE(ABORT,'V1 pool scope mismatch') END;\n SELECT CASE WHEN NEW.kind IN ('REGISTRATION','FEE_OBLIGATION','REFUND_REVIEW') AND NEW.created_by_id IS NOT NEW.owner_id\n THEN RAISE(ABORT,'Owner consent required') END;\n SELECT CASE WHEN NEW.kind='REGISTRATION' AND NOT EXISTS(\n  SELECT 1 FROM tournament_v1_records e JOIN users u ON u.id=NEW.owner_id\n   JOIN tournament_v1_policies p ON p.id=NEW.policy_id JOIN tournament_registrations r ON r.id=NEW.registration_id\n  WHERE e.id=NEW.parent_id AND e.kind='ELIGIBILITY' AND e.owner_id=u.id AND e.player_id=u.player_id\n    AND NEW.player_id=u.player_id AND r.player_id=u.player_id AND r.tournament_id=p.tournament_id AND u.is_active=1\n    AND NEW.created_at<=p.registration_deadline\n    AND (SELECT count(*) FROM tournament_v1_records x WHERE x.policy_id=p.id AND x.kind='REGISTRATION')<p.capacity\n ) THEN RAISE(ABORT,'Registration eligibility/deadline/capacity check failed') END;\n SELECT CASE WHEN NEW.kind='FEE_OBLIGATION' AND NOT EXISTS(\n  SELECT 1 FROM tournament_v1_records r JOIN tournament_v1_policies p ON p.id=r.policy_id\n  WHERE r.id=NEW.parent_id AND r.kind='REGISTRATION' AND r.owner_id=NEW.owner_id\n   AND r.registration_id=NEW.registration_id AND NEW.player_id=r.player_id AND NEW.amount_minor=p.price_minor\n ) THEN RAISE(ABORT,'One exact fee obligation per registration required') END;\n SELECT CASE WHEN NEW.kind='CONFIRMATION' AND (\n  (json_extract(NEW.data_json,'$.basis')='FREE' AND EXISTS(SELECT 1 FROM tournament_v1_policies p WHERE p.id=NEW.policy_id AND p.price_minor=0)) OR\n  (json_extract(NEW.data_json,'$.basis')='WAIVER' AND EXISTS(SELECT 1 FROM tournament_v1_records w WHERE w.parent_id=NEW.parent_id AND w.kind='WAIVER'))\n ) IS NOT 1 THEN RAISE(ABORT,'Paid confirmation requires unsupported cleared pool funding') END;\n SELECT CASE WHEN NEW.kind IN ('WAIVER','FEE_REFERENCE','SPONSOR_REVIEW','RESULTS_APPROVAL') AND NOT EXISTS(\n  SELECT 1 FROM users u WHERE u.id=NEW.created_by_id AND u.role='administrator' AND u.is_active=1\n   AND (NEW.owner_id IS NULL OR u.id!=NEW.owner_id)\n ) THEN RAISE(ABORT,'Independent active administrator required') END;\n SELECT CASE WHEN NEW.kind='FEE_REFERENCE' AND NOT EXISTS(\n  SELECT 1 FROM tournament_v1_records f JOIN financial_operations o ON o.id=NEW.operation_id\n    JOIN financial_ledger_entries e ON e.id=NEW.receipt_id JOIN tournament_v1_records r ON r.id=f.parent_id\n  WHERE f.id=NEW.parent_id AND f.kind='FEE_OBLIGATION' AND r.owner_id=o.owner_id AND NEW.owner_id=r.owner_id AND NEW.player_id=r.player_id\n   AND o.kind='fee' AND o.status='POSTED' AND o.currency='BWP' AND o.amount_minor=f.amount_minor\n   AND NEW.amount_minor=f.amount_minor AND o.receipt_id=e.id AND e.idempotency_key=o.id\n   AND e.amount_minor=o.amount_minor AND e.wallet_id=o.wallet_id AND e.kind='fee'\n   AND o.created_at>=r.created_at AND o.posted_at>=r.created_at\n   AND NEW.created_by_id!=o.requested_by_id\n ) THEN RAISE(ABORT,'Posted fee provenance mismatch; no clearing is inferred') END;\n SELECT CASE WHEN NEW.kind='REFUND_REVIEW' AND NOT EXISTS(\n  SELECT 1 FROM tournament_v1_records f WHERE f.id=NEW.parent_id AND f.kind='FEE_REFERENCE'\n   AND f.owner_id=NEW.owner_id AND NEW.amount_minor>0\n   AND NEW.amount_minor+coalesce((SELECT sum(x.amount_minor) FROM tournament_v1_records x WHERE x.parent_id=f.id AND x.kind='REFUND_REVIEW'),0)<=f.amount_minor\n ) THEN RAISE(ABORT,'Refund review exceeds original remaining principal') END;\n SELECT CASE WHEN NEW.kind='RESULTS_APPROVAL' AND NOT EXISTS(\n  SELECT 1 FROM tournament_v1_records r WHERE r.id=NEW.parent_id AND r.kind='RESULTS_REVISION'\n    AND r.created_by_id!=NEW.created_by_id\n    AND NOT EXISTS(SELECT 1 FROM json_each(r.data_json,'$.proposers') x WHERE x.value=NEW.created_by_id)\n    AND NOT EXISTS(SELECT 1 FROM json_each(r.data_json,'$.winners') x JOIN users u ON u.player_id=json_extract(x.value,'$.player_id') WHERE u.id=NEW.created_by_id)\n ) THEN RAISE(ABORT,'Independent non-beneficiary results approval required') END;\n SELECT CASE WHEN NEW.kind='PAYOUT_SCHEDULE' AND (\n  json_extract(NEW.data_json,'$.postable') IS NOT 0 OR NOT EXISTS(\n   SELECT 1 FROM tournament_v1_records a WHERE a.kind='RESULTS_APPROVAL' AND a.parent_id=NEW.parent_id)\n ) THEN RAISE(ABORT,'Only blocked preview schedules are supported') END;\nEND"
    )
    op.execute(
        "CREATE TRIGGER v1_request_scope BEFORE INSERT ON tournament_v1_requests\nBEGIN\n SELECT CASE WHEN NEW.record_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM tournament_v1_records r WHERE r.id=NEW.record_id AND r.policy_id=NEW.policy_id)\n THEN RAISE(ABORT,'V1 request scope mismatch') END;\nEND"
    )


def downgrade() -> None:
    # Refuse before dropping any trigger, index or table.
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM tournament_v1_policies LIMIT 1"))
        .first()
    ):
        raise RuntimeError(
            "Populated V1 policy records require an approved retention/rollback plan"
        )
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM tournament_pool_accounts LIMIT 1"))
        .first()
    ):
        raise RuntimeError(
            "Populated V1 policy records require an approved retention/rollback plan"
        )
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM tournament_v1_records LIMIT 1"))
        .first()
    ):
        raise RuntimeError(
            "Populated V1 policy records require an approved retention/rollback plan"
        )
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM tournament_v1_requests LIMIT 1"))
        .first()
    ):
        raise RuntimeError(
            "Populated V1 policy records require an approved retention/rollback plan"
        )

    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("tournament_v1_requests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tournament_v1_requests_policy_id"))

    op.drop_table("tournament_v1_requests")
    with op.batch_alter_table("tournament_v1_records", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tournament_v1_records_policy_id"))
        batch_op.drop_index(batch_op.f("ix_tournament_v1_records_parent_id"))

    op.drop_table("tournament_v1_records")
    op.drop_table("tournament_pool_accounts")
    op.drop_table("tournament_v1_policies")
    # ### end Alembic commands ###
