"""Password hashing, revocable token sessions and server-side permission checks."""

from datetime import timedelta, timezone
from functools import lru_cache
import hashlib
import hmac
import secrets
import uuid

from argon2 import PasswordHasher, Type
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from sqlalchemy import delete, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.auth_config import get_auth_config
from app.database import get_db
from app.models import (
    AuthAuditEvent,
    AuthRateLimit,
    AuthSession,
    RefreshToken,
    TournamentOrganiser,
    User,
)
from app.time import utc_now

PASSWORDS = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, type=Type.ID)
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return PASSWORDS.hash(password)


@lru_cache(maxsize=1)
def dummy_hash() -> str:
    return hash_password(secrets.token_urlsafe(32))


def verify_password(password: str, encoded: str) -> bool:
    try:
        return PASSWORDS.verify(encoded, password)
    except (VerificationError, InvalidHashError):
        return False


def audit(
    db: Session,
    event: str,
    success: bool,
    user_id: int | None = None,
    target_id: int | None = None,
    reason: str | None = None,
) -> None:
    db.add(
        AuthAuditEvent(
            event=event,
            success=success,
            user_id=user_id,
            target_id=target_id,
            reason=reason,
        )
    )


def unauthenticated() -> HTTPException:
    return HTTPException(
        401,
        "Session expired or invalid. Please sign in.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def browser_request(request: Request) -> None:
    config = get_auth_config()
    if request.headers.get("X-Snooker-Client") != "web":
        raise HTTPException(
            403, "Authentication requests require X-Snooker-Client: web"
        )
    origin = request.headers.get("origin")
    if (origin and origin not in config.origins) or request.headers.get(
        "sec-fetch-site"
    ) == "cross-site":
        raise HTTPException(403, "Untrusted authentication request origin")


def throttle(db: Session, request: Request, operation: str, username: str = "") -> None:
    """SQLite-backed bounded buckets, independent of untrusted forwarded headers."""
    now = utc_now()
    window = int(now.replace(tzinfo=timezone.utc).timestamp()) // 60
    subjects = [(request.client.host if request.client else "unknown", 30)]
    if username:
        subjects.append(("username:" + username, 10))
    db.execute(delete(AuthRateLimit).where(AuthRateLimit.expires_at < now))
    exceeded = False
    for subject, limit in subjects:
        key = hmac.new(
            get_auth_config().secret.encode(),
            f"{operation}|{subject}|{window}".encode(),
            hashlib.sha256,
        ).hexdigest()
        statement = insert(AuthRateLimit).values(
            bucket=key, attempts=1, expires_at=now + timedelta(minutes=2)
        )
        statement = statement.on_conflict_do_update(
            index_elements=[AuthRateLimit.bucket],
            set_={"attempts": AuthRateLimit.attempts + 1},
        ).returning(AuthRateLimit.attempts)
        exceeded |= db.execute(statement).scalar_one() > limit
    db.commit()
    if exceeded:
        audit(db, "auth_rate_limited", False)
        db.commit()
        raise HTTPException(
            429,
            "Too many authentication attempts. Try again shortly.",
            headers={"Retry-After": "60"},
        )


def refresh_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def access_token(user: User, session: AuthSession) -> str:
    config = get_auth_config()
    issued = utc_now().replace(tzinfo=timezone.utc)
    return jwt.encode(
        {
            "sub": str(user.id),
            "sid": session.id,
            "iat": issued,
            "exp": issued + timedelta(seconds=config.access_seconds),
            "iss": config.issuer,
            "aud": config.audience,
            "jti": str(uuid.uuid4()),
        },
        config.secret,
        algorithm="HS256",
    )


def make_refresh(db: Session, session: AuthSession) -> str:
    raw = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            token_hash=refresh_digest(raw),
            session_id=session.id,
            expires_at=session.expires_at,
        )
    )
    return raw


def create_session(db: Session, user: User) -> tuple[str, str]:
    session = AuthSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        expires_at=utc_now() + timedelta(seconds=get_auth_config().refresh_seconds),
    )
    db.add(session)
    db.flush()
    raw = make_refresh(db, session)
    return access_token(user, session), raw


def token_identity(db: Session, token: str) -> tuple[User, AuthSession]:
    config = get_auth_config()
    try:
        claims = jwt.decode(
            token,
            config.secret,
            algorithms=["HS256"],
            issuer=config.issuer,
            audience=config.audience,
            options={"require": ["sub", "sid", "iat", "exp", "jti", "iss", "aud"]},
        )
        user = db.get(User, int(claims["sub"]))
        session = db.get(AuthSession, claims["sid"])
        if (
            not user
            or not user.is_active
            or not session
            or session.user_id != user.id
            or session.revoked_at
            or session.expires_at <= utc_now()
        ):
            raise unauthenticated()
        return user, session
    except (jwt.InvalidTokenError, ValueError, TypeError, KeyError):
        raise unauthenticated() from None


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthenticated()
    return token_identity(db, credentials.credentials)[0]


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "administrator":
        raise HTTPException(403, "Administrator permission required")
    return user


def player_permission(user: User, player_id: int) -> None:
    if user.role != "administrator" and user.player_id != player_id:
        raise HTTPException(403, "Access to this player is not permitted")


def tournament_permission(db: Session, user: User, tournament_id: int) -> None:
    if user.role == "administrator":
        return
    if (
        user.role != "organiser"
        or db.get(TournamentOrganiser, (tournament_id, user.id)) is None
    ):
        raise HTTPException(403, "Assigned tournament organiser permission required")


def financial_disabled() -> None:
    raise HTTPException(
        403,
        detail={
            "code": "FINANCIAL_OPERATIONS_DISABLED",
            "message": "Financial mutations are disabled until Task 04 integrity controls are verified.",
        },
    )


def revoke_user_sessions(db: Session, user_id: int) -> None:
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=utc_now())
    )
