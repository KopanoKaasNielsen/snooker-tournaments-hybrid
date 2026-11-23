"""Policy-neutral tournament review metadata; no monetary rule is implemented."""

from sqlalchemy import DDL, event, inspect, text

TRIGGERS = {
    "tournament_intent_scope": """CREATE TRIGGER tournament_intent_scope BEFORE INSERT ON tournament_financial_intents
    BEGIN
      SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM users u WHERE u.id=NEW.requested_by_id AND u.is_active=1
        AND (u.role='administrator' OR (u.role='organiser' AND EXISTS (
          SELECT 1 FROM tournament_organisers a WHERE a.user_id=u.id AND a.tournament_id=NEW.tournament_id))))
        THEN RAISE(ABORT, 'Assigned tournament authority required') END;
      SELECT CASE WHEN NEW.kind IN ('FEE','REFUND') AND NOT EXISTS (
        SELECT 1 FROM tournament_registrations r WHERE r.id=NEW.registration_id
          AND r.tournament_id=NEW.tournament_id AND r.player_id=NEW.player_id)
        THEN RAISE(ABORT, 'Registration review scope mismatch') END;
      SELECT CASE WHEN NEW.kind='PAYOUT' AND NOT EXISTS (
        SELECT 1 FROM tournament_results r WHERE r.id=NEW.result_id
          AND r.tournament_id=NEW.tournament_id AND r.player_id=NEW.player_id)
        THEN RAISE(ABORT, 'Result review scope mismatch') END;
    END""",
    "tournament_intent_no_update": """CREATE TRIGGER tournament_intent_no_update BEFORE UPDATE ON tournament_financial_intents
      BEGIN SELECT RAISE(ABORT, 'Policy-blocked intent is immutable'); END""",
    "tournament_intent_no_delete": """CREATE TRIGGER tournament_intent_no_delete BEFORE DELETE ON tournament_financial_intents
      BEGIN SELECT RAISE(ABORT, 'Policy-blocked intent cannot be deleted'); END""",
    "tournament_request_scope": """CREATE TRIGGER tournament_request_scope BEFORE INSERT ON tournament_financial_requests
    BEGIN
      SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM tournament_financial_intents i JOIN users u ON u.id=NEW.requested_by_id
        WHERE i.id=NEW.intent_id AND u.is_active=1 AND u.role=NEW.actor_role AND
        (u.role='administrator' OR (u.role='organiser' AND EXISTS (
          SELECT 1 FROM tournament_organisers a WHERE a.user_id=u.id AND a.tournament_id=i.tournament_id))))
        THEN RAISE(ABORT, 'Assigned tournament review authority required') END;
    END""",
    "tournament_request_no_update": """CREATE TRIGGER tournament_request_no_update BEFORE UPDATE ON tournament_financial_requests
      BEGIN SELECT RAISE(ABORT, 'Tournament review request is immutable'); END""",
    "tournament_request_no_delete": """CREATE TRIGGER tournament_request_no_delete BEFORE DELETE ON tournament_financial_requests
      BEGIN SELECT RAISE(ABORT, 'Tournament review request cannot be deleted'); END""",
}


def attach_triggers(table):
    request = table.name == "tournament_financial_requests"
    for name, sql in TRIGGERS.items():
        if name.startswith("tournament_request_") == request:
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


def key_reserved(connection, key: str) -> bool:
    if not inspect(connection).has_table("tournament_financial_intents"):
        return False
    reserved = (
        connection.execute(
            text(
                "SELECT 1 FROM tournament_financial_intents WHERE id=:key UNION ALL SELECT 1 FROM tournament_financial_requests WHERE idempotency_key=:key LIMIT 1"
            ),
            {"key": key},
        ).first()
        is not None
    )
    if reserved:
        return True
    from app.tournament_v1_schema import key_reserved as v1_reserved

    return v1_reserved(connection, key)
