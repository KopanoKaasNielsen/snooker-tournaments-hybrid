"""Additive SQLite operation state/ownership/receipt and audit protections."""

from sqlalchemy import DDL, event, text

OPERATION_TRIGGERS = {
    "operation_insert_guard": """CREATE TRIGGER operation_insert_guard BEFORE INSERT ON financial_operations
    BEGIN
      SELECT CASE WHEN NEW.status != 'PENDING' OR NEW.last_actor_id != NEW.requested_by_id
        THEN RAISE(ABORT, 'Operations must start pending') END;
      SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM users u JOIN financial_wallets w ON w.player_id=u.player_id
        WHERE u.id=NEW.owner_id AND u.is_active=1 AND w.id=NEW.wallet_id AND w.currency=NEW.currency
      ) THEN RAISE(ABORT, 'Operation owner does not own wallet') END;
      SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM users u WHERE u.id=NEW.requested_by_id AND u.is_active=1 AND (
          (NEW.kind IN ('deposit','withdrawal') AND u.id=NEW.owner_id) OR
          (NEW.kind IN ('fee','prize') AND u.role='administrator' AND u.id!=NEW.owner_id)
        )
      ) THEN RAISE(ABORT, 'Operation requester permission denied') END;
    END""",
    "operation_update_guard": """CREATE TRIGGER operation_update_guard BEFORE UPDATE ON financial_operations
    BEGIN
      SELECT CASE WHEN NEW.id IS NOT OLD.id OR NEW.idempotency_key IS NOT OLD.idempotency_key
        OR NEW.owner_id IS NOT OLD.owner_id OR NEW.requested_by_id IS NOT OLD.requested_by_id
        OR NEW.wallet_id IS NOT OLD.wallet_id OR NEW.amount_minor IS NOT OLD.amount_minor
        OR NEW.currency IS NOT OLD.currency OR NEW.kind IS NOT OLD.kind OR NEW.created_at IS NOT OLD.created_at
        THEN RAISE(ABORT, 'Operation intent is immutable') END;
      SELECT CASE WHEN NOT (
        (OLD.status='PENDING' AND NEW.status IN ('VERIFIED','REJECTED','CANCELLED')) OR
        (OLD.status='VERIFIED' AND NEW.status IN ('POSTED','REJECTED'))
      ) THEN RAISE(ABORT, 'Invalid operation transition') END;
      SELECT CASE WHEN OLD.verified_at IS NOT NULL AND (
        NEW.verified_at IS NOT OLD.verified_at OR NEW.verified_by_id IS NOT OLD.verified_by_id
        OR NEW.provider IS NOT OLD.provider OR NEW.provider_event_digest IS NOT OLD.provider_event_digest
        OR NEW.provider_payload_digest IS NOT OLD.provider_payload_digest OR NEW.reference_digest IS NOT OLD.reference_digest
      ) THEN RAISE(ABORT, 'Verified evidence is immutable') END;
      SELECT CASE WHEN NOT EXISTS (SELECT 1 FROM users a WHERE a.id=NEW.last_actor_id AND a.is_active=1)
        THEN RAISE(ABORT, 'Inactive operation actor') END;
      SELECT CASE WHEN NEW.status IN ('VERIFIED','POSTED') AND NOT EXISTS (
        SELECT 1 FROM users a JOIN users o ON o.id=NEW.owner_id JOIN financial_wallets w ON w.player_id=o.player_id
        WHERE a.id=NEW.last_actor_id AND a.role='administrator' AND a.is_active=1
          AND a.id!=NEW.owner_id AND a.id!=NEW.requested_by_id AND o.is_active=1 AND w.id=NEW.wallet_id
      ) THEN RAISE(ABORT, 'Independent active financial reviewer required') END;
      SELECT CASE WHEN NEW.status='VERIFIED' AND NEW.verified_by_id!=NEW.last_actor_id
        THEN RAISE(ABORT, 'Verification actor mismatch') END;
      SELECT CASE WHEN NEW.status='POSTED' AND (NEW.posted_by_id!=NEW.last_actor_id OR NOT EXISTS (
        SELECT 1 FROM users v WHERE v.id=NEW.verified_by_id AND v.is_active=1 AND v.role='administrator'
      )) THEN RAISE(ABORT, 'Posting reviewer mismatch') END;
      SELECT CASE WHEN NEW.status='POSTED' AND NOT EXISTS (
        SELECT 1 FROM financial_ledger_entries e WHERE e.id=NEW.receipt_id
          AND e.idempotency_key=NEW.id AND e.wallet_id=NEW.wallet_id AND e.currency=NEW.currency
          AND e.kind=NEW.kind AND e.amount_minor=NEW.amount_minor
      ) THEN RAISE(ABORT, 'Posted operation must match ledger receipt') END;
      SELECT CASE WHEN NEW.status='REJECTED' AND NOT EXISTS (
        SELECT 1 FROM users a WHERE a.id=NEW.last_actor_id AND a.role='administrator' AND a.is_active=1
      ) THEN RAISE(ABORT, 'Rejection requires administrator') END;
      SELECT CASE WHEN NEW.status='CANCELLED' AND NOT EXISTS (
        SELECT 1 FROM users a WHERE a.id=NEW.last_actor_id AND a.is_active=1 AND (a.id=NEW.owner_id OR a.role='administrator')
      ) THEN RAISE(ABORT, 'Cancellation permission denied') END;
      SELECT CASE WHEN NEW.updated_at < OLD.updated_at THEN RAISE(ABORT, 'Operation time cannot regress') END;
    END""",
    "operation_no_delete": """CREATE TRIGGER operation_no_delete BEFORE DELETE ON financial_operations
        BEGIN SELECT RAISE(ABORT, 'Operations cannot be deleted'); END""",
    "operation_audit_insert_guard": """CREATE TRIGGER operation_audit_insert_guard BEFORE INSERT ON financial_operation_audit
    BEGIN
      SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM financial_operations o JOIN users u ON u.id=NEW.actor_id
        WHERE o.id=NEW.operation_id AND o.status=NEW.to_status AND o.last_actor_id=NEW.actor_id
          AND u.role=NEW.actor_role AND (
            (NEW.event='created' AND NEW.from_status IS NULL AND NEW.to_status='PENDING' AND NEW.reason_code='requested') OR
            (NEW.event='verified' AND NEW.from_status='PENDING' AND NEW.to_status='VERIFIED' AND NEW.reason_code='evidence_verified') OR
            (NEW.event='posted' AND NEW.from_status='VERIFIED' AND NEW.to_status='POSTED' AND NEW.reason_code='posted') OR
            (NEW.event='rejected' AND NEW.from_status IN ('PENDING','VERIFIED') AND NEW.to_status='REJECTED' AND NEW.reason_code='policy_rejected') OR
            (NEW.event='cancelled' AND NEW.from_status='PENDING' AND NEW.to_status='CANCELLED' AND NEW.reason_code IN ('owner_cancelled','admin_cancelled'))
          )
      ) THEN RAISE(ABORT, 'Audit must match durable operation transition') END;
    END""",
    "operation_audit_no_update": """CREATE TRIGGER operation_audit_no_update BEFORE UPDATE ON financial_operation_audit
        BEGIN SELECT RAISE(ABORT, 'Financial operation audit is append-only'); END""",
    "operation_audit_no_delete": """CREATE TRIGGER operation_audit_no_delete BEFORE DELETE ON financial_operation_audit
        BEGIN SELECT RAISE(ABORT, 'Financial operation audit is append-only'); END""",
}


def attach_operation_triggers(table) -> None:
    audit = table.name == "financial_operation_audit"
    for name, statement in OPERATION_TRIGGERS.items():
        if name.startswith("operation_audit_") == audit:
            event.listen(
                table, "after_create", DDL(statement).execute_if(dialect="sqlite")
            )


def operation_triggers_match(connection) -> bool:
    actual = dict(
        connection.execute(
            text("SELECT name, sql FROM sqlite_master WHERE type='trigger'")
        ).all()
    )
    return all(
        name in actual and " ".join(actual[name].split()) == " ".join(sql.split())
        for name, sql in OPERATION_TRIGGERS.items()
    )
