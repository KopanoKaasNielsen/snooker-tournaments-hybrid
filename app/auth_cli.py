"""Offline, explicit first-administrator creation. No public role escalation."""

import argparse
import getpass

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.auth_config import get_auth_config
from app.auth_schemas import RegisterRequest
from app.database import SessionLocal, engine
from app.models import User
from app.security import audit, hash_password


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["create-admin"])
    parser.add_argument("--username", required=True)
    args = parser.parse_args()
    get_auth_config()
    password = getpass.getpass("Administrator password (15–128 characters): ")
    if password != getpass.getpass("Confirm password: "):
        parser.error("Passwords do not match")
    try:
        payload = RegisterRequest(
            username=args.username, password=password, create_player=False
        )
    except ValidationError:
        parser.error("Username/password do not meet the documented requirements")
    try:
        with SessionLocal() as db:
            user = User(
                username=payload.username,
                password_hash=hash_password(password),
                role="administrator",
            )
            db.add(user)
            db.flush()
            audit(
                db,
                "administrator_bootstrap",
                True,
                user.id,
                user.id,
                "offline_operator",
            )
            db.commit()
        print("Administrator account created; no player records linked.")
    except IntegrityError:
        parser.error("Username already exists; existing accounts were not changed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
