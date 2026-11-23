"""SQLite V1 metadata protections and legacy-workflow isolation."""

from sqlalchemy import DDL, event, inspect, text
from fastapi import HTTPException

TABLES = (
    "tournament_v1_policies",
    "tournament_pool_accounts",
    "tournament_v1_records",
    "tournament_v1_requests",
)
TRIGGERS = {}
for table in TABLES:
    for verb in ("UPDATE", "DELETE"):
        name = table + "_" + verb.lower() + "_blocked"
        TRIGGERS[name] = (
            f"CREATE TRIGGER {name} BEFORE {verb} ON {table} BEGIN SELECT RAISE(ABORT, 'V1 financial records are immutable'); END"
        )

TRIGGERS[
    "v1_policy_new_only"
] = """CREATE TRIGGER v1_policy_new_only BEFORE INSERT ON tournament_v1_policies
BEGIN
 SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM tournaments t JOIN users u ON u.id=NEW.created_by_id
  WHERE t.id=NEW.tournament_id AND t.created_at=NEW.created_at AND t.status='PENDING' AND t.entry_fee=0
   AND u.is_active=1 AND u.role IN ('organiser','administrator'))
  OR EXISTS(SELECT 1 FROM tournament_registrations r WHERE r.tournament_id=NEW.tournament_id)
  OR EXISTS(SELECT 1 FROM matches m WHERE m.tournament_id=NEW.tournament_id)
  OR EXISTS(SELECT 1 FROM tournament_results r WHERE r.tournament_id=NEW.tournament_id)
 THEN RAISE(ABORT,'Explicit newly created tournament policy required') END;
END"""
TRIGGERS[
    "v1_record_scope"
] = """CREATE TRIGGER v1_record_scope BEFORE INSERT ON tournament_v1_records
BEGIN
 SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.created_by_id AND u.is_active=1)
 THEN RAISE(ABORT,'Active V1 actor required') END;
 SELECT CASE WHEN NEW.kind IN ('ELIGIBILITY','MATCH_RESULT','RESULTS_REVISION','CANCELLATION','PAYOUT_SCHEDULE') AND NOT EXISTS(
  SELECT 1 FROM users u JOIN tournament_v1_policies p ON p.id=NEW.policy_id WHERE u.id=NEW.created_by_id AND u.is_active=1
   AND (u.role='administrator' OR (u.role='organiser' AND EXISTS(SELECT 1 FROM tournament_organisers a WHERE a.user_id=u.id AND a.tournament_id=p.tournament_id)))
 ) THEN RAISE(ABORT,'Assigned V1 authority required') END;
 SELECT CASE WHEN NEW.kind IN ('FEE_OBLIGATION','CONFIRMATION','WAIVER','FEE_REFERENCE','RESULTS_APPROVAL','PAYOUT_SCHEDULE') AND (
   NEW.parent_id IS NULL OR NEW.identity_key IS NOT NEW.parent_id OR EXISTS(SELECT 1 FROM tournament_v1_records x WHERE x.policy_id=NEW.policy_id AND x.kind=NEW.kind AND x.parent_id=NEW.parent_id))
 THEN RAISE(ABORT,'Unique immutable parent identity required') END;
 SELECT CASE WHEN NEW.kind IN ('REGISTRATION','ELIGIBILITY') AND NEW.identity_key IS NOT CAST(NEW.owner_id AS TEXT)
 THEN RAISE(ABORT,'Unique owner identity required') END;
 SELECT CASE WHEN NEW.kind IN ('CONFIRMATION','WAIVER') AND NOT EXISTS(SELECT 1 FROM tournament_v1_records r WHERE r.id=NEW.parent_id AND r.kind='REGISTRATION' AND r.owner_id=NEW.owner_id AND r.player_id=NEW.player_id)
 THEN RAISE(ABORT,'Confirmation/waiver registration scope mismatch') END;
 SELECT CASE WHEN NEW.kind='FEE_REFERENCE' AND (NEW.amount_minor<=0 OR json_extract(NEW.data_json,'$.cleared') IS NOT 0)
 THEN RAISE(ABORT,'Fee reference cannot imply clearing') END;
 SELECT CASE WHEN NEW.kind='REFUND_REVIEW' AND json_extract(NEW.data_json,'$.refunded_minor') IS NOT 0
 THEN RAISE(ABORT,'Refund reviews cannot imply money movement') END;
 SELECT CASE WHEN NEW.match_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM matches m JOIN tournament_v1_policies p ON p.id=NEW.policy_id WHERE m.id=NEW.match_id AND m.tournament_id=p.tournament_id)
 THEN RAISE(ABORT,'V1 match scope mismatch') END;
 SELECT CASE WHEN NEW.kind='ELIGIBILITY' AND NOT EXISTS(SELECT 1 FROM users u WHERE u.id=NEW.owner_id AND u.is_active=1 AND u.player_id=NEW.player_id AND u.id!=NEW.created_by_id)
 THEN RAISE(ABORT,'Independent eligibility review required') END;
 SELECT CASE WHEN NEW.parent_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM tournament_v1_records p WHERE p.id=NEW.parent_id AND p.policy_id=NEW.policy_id)
 THEN RAISE(ABORT,'V1 parent scope mismatch') END;
 SELECT CASE WHEN NEW.pool_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM tournament_pool_accounts p WHERE p.id=NEW.pool_id AND p.policy_id=NEW.policy_id)
 THEN RAISE(ABORT,'V1 pool scope mismatch') END;
 SELECT CASE WHEN NEW.kind IN ('REGISTRATION','FEE_OBLIGATION','REFUND_REVIEW') AND NEW.created_by_id IS NOT NEW.owner_id
 THEN RAISE(ABORT,'Owner consent required') END;
 SELECT CASE WHEN NEW.kind='REGISTRATION' AND NOT EXISTS(
  SELECT 1 FROM tournament_v1_records e JOIN users u ON u.id=NEW.owner_id
   JOIN tournament_v1_policies p ON p.id=NEW.policy_id JOIN tournament_registrations r ON r.id=NEW.registration_id
  WHERE e.id=NEW.parent_id AND e.kind='ELIGIBILITY' AND e.owner_id=u.id AND e.player_id=u.player_id
    AND NEW.player_id=u.player_id AND r.player_id=u.player_id AND r.tournament_id=p.tournament_id AND u.is_active=1
    AND NEW.created_at<=p.registration_deadline
    AND (SELECT count(*) FROM tournament_v1_records x WHERE x.policy_id=p.id AND x.kind='REGISTRATION')<p.capacity
 ) THEN RAISE(ABORT,'Registration eligibility/deadline/capacity check failed') END;
 SELECT CASE WHEN NEW.kind='FEE_OBLIGATION' AND NOT EXISTS(
  SELECT 1 FROM tournament_v1_records r JOIN tournament_v1_policies p ON p.id=r.policy_id
  WHERE r.id=NEW.parent_id AND r.kind='REGISTRATION' AND r.owner_id=NEW.owner_id
   AND r.registration_id=NEW.registration_id AND NEW.player_id=r.player_id AND NEW.amount_minor=p.price_minor
 ) THEN RAISE(ABORT,'One exact fee obligation per registration required') END;
 SELECT CASE WHEN NEW.kind='CONFIRMATION' AND (
  (json_extract(NEW.data_json,'$.basis')='FREE' AND EXISTS(SELECT 1 FROM tournament_v1_policies p WHERE p.id=NEW.policy_id AND p.price_minor=0)) OR
  (json_extract(NEW.data_json,'$.basis')='WAIVER' AND EXISTS(SELECT 1 FROM tournament_v1_records w WHERE w.parent_id=NEW.parent_id AND w.kind='WAIVER'))
 ) IS NOT 1 THEN RAISE(ABORT,'Paid confirmation requires unsupported cleared pool funding') END;
 SELECT CASE WHEN NEW.kind IN ('WAIVER','FEE_REFERENCE','SPONSOR_REVIEW','RESULTS_APPROVAL') AND NOT EXISTS(
  SELECT 1 FROM users u WHERE u.id=NEW.created_by_id AND u.role='administrator' AND u.is_active=1
   AND (NEW.owner_id IS NULL OR u.id!=NEW.owner_id)
 ) THEN RAISE(ABORT,'Independent active administrator required') END;
 SELECT CASE WHEN NEW.kind='FEE_REFERENCE' AND NOT EXISTS(
  SELECT 1 FROM tournament_v1_records f JOIN financial_operations o ON o.id=NEW.operation_id
    JOIN financial_ledger_entries e ON e.id=NEW.receipt_id JOIN tournament_v1_records r ON r.id=f.parent_id
  WHERE f.id=NEW.parent_id AND f.kind='FEE_OBLIGATION' AND r.owner_id=o.owner_id AND NEW.owner_id=r.owner_id AND NEW.player_id=r.player_id
   AND o.kind='fee' AND o.status='POSTED' AND o.currency='BWP' AND o.amount_minor=f.amount_minor
   AND NEW.amount_minor=f.amount_minor AND o.receipt_id=e.id AND e.idempotency_key=o.id
   AND e.amount_minor=o.amount_minor AND e.wallet_id=o.wallet_id AND e.kind='fee'
   AND o.created_at>=r.created_at AND o.posted_at>=r.created_at
   AND NEW.created_by_id!=o.requested_by_id
 ) THEN RAISE(ABORT,'Posted fee provenance mismatch; no clearing is inferred') END;
 SELECT CASE WHEN NEW.kind='REFUND_REVIEW' AND NOT EXISTS(
  SELECT 1 FROM tournament_v1_records f WHERE f.id=NEW.parent_id AND f.kind='FEE_REFERENCE'
   AND f.owner_id=NEW.owner_id AND NEW.amount_minor>0
   AND NEW.amount_minor+coalesce((SELECT sum(x.amount_minor) FROM tournament_v1_records x WHERE x.parent_id=f.id AND x.kind='REFUND_REVIEW'),0)<=f.amount_minor
 ) THEN RAISE(ABORT,'Refund review exceeds original remaining principal') END;
 SELECT CASE WHEN NEW.kind='RESULTS_APPROVAL' AND NOT EXISTS(
  SELECT 1 FROM tournament_v1_records r WHERE r.id=NEW.parent_id AND r.kind='RESULTS_REVISION'
    AND r.created_by_id!=NEW.created_by_id
    AND NOT EXISTS(SELECT 1 FROM json_each(r.data_json,'$.proposers') x WHERE x.value=NEW.created_by_id)
    AND NOT EXISTS(SELECT 1 FROM json_each(r.data_json,'$.winners') x JOIN users u ON u.player_id=json_extract(x.value,'$.player_id') WHERE u.id=NEW.created_by_id)
 ) THEN RAISE(ABORT,'Independent non-beneficiary results approval required') END;
 SELECT CASE WHEN NEW.kind='PAYOUT_SCHEDULE' AND (
  json_extract(NEW.data_json,'$.postable') IS NOT 0 OR NOT EXISTS(
   SELECT 1 FROM tournament_v1_records a WHERE a.kind='RESULTS_APPROVAL' AND a.parent_id=NEW.parent_id)
 ) THEN RAISE(ABORT,'Only blocked preview schedules are supported') END;
END"""
TRIGGERS[
    "v1_request_scope"
] = """CREATE TRIGGER v1_request_scope BEFORE INSERT ON tournament_v1_requests
BEGIN
 SELECT CASE WHEN NEW.record_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM tournament_v1_records r WHERE r.id=NEW.record_id AND r.policy_id=NEW.policy_id)
 THEN RAISE(ABORT,'V1 request scope mismatch') END;
END"""


def attach_v1_triggers(table):
    for name, sql in TRIGGERS.items():
        own = (
            name.startswith(table.name + "_")
            or (table.name == "tournament_v1_policies" and name == "v1_policy_new_only")
            or (table.name == "tournament_v1_records" and name == "v1_record_scope")
            or (table.name == "tournament_v1_requests" and name == "v1_request_scope")
        )
        if own:
            event.listen(table, "after_create", DDL(sql).execute_if(dialect="sqlite"))


def triggers_match(connection):
    actual = dict(
        connection.execute(
            text("SELECT name,sql FROM sqlite_master WHERE type='trigger'")
        ).all()
    )
    return all(
        name in actual and " ".join(actual[name].split()) == " ".join(sql.split())
        for name, sql in TRIGGERS.items()
    )


def key_reserved(connection, key):
    if not inspect(connection).has_table("tournament_v1_policies"):
        return False
    return (
        connection.execute(
            text(
                "SELECT 1 FROM tournament_v1_policies WHERE id=:key UNION ALL SELECT 1 FROM tournament_pool_accounts WHERE id=:key UNION ALL SELECT 1 FROM tournament_v1_records WHERE id=:key UNION ALL SELECT 1 FROM tournament_v1_requests WHERE idempotency_key=:key LIMIT 1"
            ),
            {"key": key},
        ).first()
        is not None
    )


def is_v1(db, tournament_id):
    return (
        inspect(db.connection()).has_table("tournament_v1_policies")
        and db.execute(
            text("SELECT 1 FROM tournament_v1_policies WHERE tournament_id=:id"),
            {"id": tournament_id},
        ).first()
        is not None
    )


def require_legacy_tournament(db, tournament_id):
    if is_v1(db, tournament_id):
        raise HTTPException(
            403,
            "V1 tournament mutations require the internal policy workflow; financial HTTP actions remain disabled",
        )
