from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth_config import get_auth_config
from app.auth_schemas import LoginRequest, RegisterRequest, TokenOut, UserOut
from app.database import get_db
from app.models import AuthSession, Player, RefreshToken, User
from app.security import (
    PASSWORDS,
    access_token,
    audit,
    browser_request,
    create_session,
    current_user,
    dummy_hash,
    hash_password,
    make_refresh,
    refresh_digest,
    revoke_user_sessions,
    throttle,
    token_identity,
    unauthenticated,
    verify_password,
)
from app.time import utc_now

router = APIRouter(prefix="/auth", tags=["authentication"])


def clear_cookie(response: Response) -> None:
    config = get_auth_config()
    response.delete_cookie(
        config.cookie_name,
        path="/",
        secure=config.secure_cookie,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"


def set_cookie(response: Response, raw: str, expires=None) -> None:
    config = get_auth_config()
    expires = expires or utc_now() + timedelta(seconds=config.refresh_seconds)
    response.set_cookie(
        config.cookie_name,
        raw,
        path="/",
        httponly=True,
        secure=config.secure_cookie,
        samesite="strict",
        max_age=max(0, int((expires - utc_now()).total_seconds())),
        expires=expires.replace(tzinfo=timezone.utc),
    )
    response.headers["Cache-Control"] = "no-store"


def prevent_last_admin(db: Session, target: User) -> None:
    if target.role == "administrator" and target.is_active:
        # Serialize administrator removal checks on the supported SQLite backend.
        db.execute(
            update(User)
            .where(User.role == "administrator")
            .values(role="administrator")
        )
        db.refresh(target)
        others = (
            db.query(User)
            .filter(
                User.role == "administrator",
                User.is_active.is_(True),
                User.id != target.id,
            )
            .count()
        )
        if not others:
            raise HTTPException(409, "The last active administrator cannot be removed")


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    dependencies=[Depends(browser_request)],
)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    throttle(db, request, "register", payload.username)
    name = (payload.player_name or payload.username).strip()
    if payload.create_player and not name:
        raise HTTPException(422, "Player name must not be blank")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role="player",
    )
    try:
        if payload.create_player:
            player = Player(name=name)
            db.add(player)
            db.flush()
            user.player_id = player.id
        db.add(user)
        db.flush()
        audit(db, "registration", True, user.id)
        db.commit()
        return user
    except IntegrityError:
        db.rollback()
        audit(db, "registration", False, reason="identifier_unavailable")
        db.commit()
        raise HTTPException(409, "Username or player name is unavailable") from None


@router.post("/login", response_model=TokenOut, dependencies=[Depends(browser_request)])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    throttle(db, request, "login", payload.username)
    user = db.query(User).filter_by(username=payload.username).first()
    valid = verify_password(
        payload.password, user.password_hash if user else dummy_hash()
    )
    if not valid or not user or not user.is_active:
        audit(
            db, "login", False, user.id if user else None, reason="invalid_credentials"
        )
        db.commit()
        raise HTTPException(
            401, "Invalid username or password", headers={"WWW-Authenticate": "Bearer"}
        )
    if PASSWORDS.check_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    token, refresh = create_session(db, user)
    audit(db, "login", True, user.id)
    db.commit()
    set_cookie(response, refresh)
    return TokenOut(access_token=token, user=UserOut.model_validate(user))


@router.post(
    "/refresh", response_model=TokenOut, dependencies=[Depends(browser_request)]
)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    throttle(db, request, "refresh")
    raw = request.cookies.get(get_auth_config().cookie_name, "")
    token = (
        db.query(RefreshToken).filter_by(token_hash=refresh_digest(raw)).first()
        if raw
        else None
    )
    session = db.get(AuthSession, token.session_id) if token else None
    user = db.get(User, session.user_id) if session else None
    now = utc_now()
    if token and token.consumed_at is not None:
        if session and session.revoked_at is None:
            session.revoked_at = now
        audit(db, "refresh_replay", False, user.id if user else None)
        db.commit()
        raise unauthenticated()
    if (
        not token
        or not session
        or not user
        or not user.is_active
        or session.revoked_at
        or token.expires_at <= now
        or session.expires_at <= now
    ):
        audit(db, "refresh", False, user.id if user else None, reason="invalid_session")
        db.commit()
        raise unauthenticated()
    consumed = db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == token.id, RefreshToken.consumed_at.is_(None))
        .values(consumed_at=now)
    )
    if consumed.rowcount != 1:
        session.revoked_at = now
        audit(db, "refresh_replay", False, user.id)
        db.commit()
        raise unauthenticated()
    rotated = make_refresh(db, session)
    jwt_token = access_token(user, session)
    audit(db, "refresh", True, user.id)
    db.commit()
    set_cookie(response, rotated, session.expires_at)
    return TokenOut(access_token=jwt_token, user=UserOut.model_validate(user))


@router.post("/logout", status_code=204, dependencies=[Depends(browser_request)])
def logout(request: Request, db: Session = Depends(get_db)):
    session = None
    raw = request.cookies.get(get_auth_config().cookie_name, "")
    token = (
        db.query(RefreshToken).filter_by(token_hash=refresh_digest(raw)).first()
        if raw
        else None
    )
    if token:
        session = db.get(AuthSession, token.session_id)
    if session is None:
        authorization = request.headers.get("authorization", "")
        if authorization.startswith("Bearer "):
            try:
                _, session = token_identity(db, authorization[7:])
            except HTTPException:
                pass
    if session:
        session.revoked_at = utc_now()
        audit(db, "logout", True, session.user_id)
        db.commit()
    response = Response(status_code=204)
    clear_cookie(response)
    return response


@router.get("/me", response_model=UserOut)
def me(response: Response, user: User = Depends(current_user)):
    response.headers["Cache-Control"] = "no-store"
    return user


@router.post("/me/deactivate", status_code=204)
def deactivate_me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    prevent_last_admin(db, user)
    user.is_active = False
    revoke_user_sessions(db, user.id)
    audit(db, "account_deactivated", True, user.id, user.id)
    db.commit()
    response = Response(status_code=204)
    clear_cookie(response)
    return response
