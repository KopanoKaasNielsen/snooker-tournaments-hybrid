from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth_schemas import OrganiserAssignment, RoleChange, UserOut
from app.database import get_db
from app.models import AuthAuditEvent, Tournament, TournamentOrganiser, User
from app.routes.auth import prevent_last_admin
from app.security import audit, require_admin, revoke_user_sessions

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/users", response_model=list[UserOut])
def users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).order_by(User.id).all()


@router.put("/users/{user_id}/role", response_model=UserOut)
def set_role(
    user_id: int,
    payload: RoleChange,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if payload.role.value != user.role:
        prevent_last_admin(db, user)
        user.role = payload.role.value
        revoke_user_sessions(db, user.id)
    audit(db, "role_changed", True, admin.id, user.id, payload.role.value)
    db.commit()
    return user


@router.post("/users/{user_id}/deactivate", status_code=204)
def deactivate(
    user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    prevent_last_admin(db, user)
    user.is_active = False
    revoke_user_sessions(db, user.id)
    audit(db, "account_deactivated", True, admin.id, user.id)
    db.commit()


@router.put("/tournaments/{tournament_id}/organisers", status_code=204)
def assign_organiser(
    tournament_id: int,
    payload: OrganiserAssignment,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tournament = db.get(Tournament, tournament_id)
    user = db.get(User, payload.user_id)
    if not tournament or not user:
        raise HTTPException(404, "Tournament or user not found")
    if not user.is_active or user.role != "organiser":
        raise HTTPException(409, "Assignment requires an active organiser")
    if db.get(TournamentOrganiser, (tournament_id, user.id)) is None:
        db.add(TournamentOrganiser(tournament_id=tournament_id, user_id=user.id))
    audit(
        db,
        "organiser_assigned",
        True,
        admin.id,
        tournament_id,
        f"organiser_id={user.id}",
    )
    db.commit()


@router.delete("/tournaments/{tournament_id}/organisers/{user_id}", status_code=204)
def unassign_organiser(
    tournament_id: int,
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    assignment = db.get(TournamentOrganiser, (tournament_id, user_id))
    if not assignment:
        raise HTTPException(404, "Assignment not found")
    db.delete(assignment)
    audit(
        db,
        "organiser_unassigned",
        True,
        admin.id,
        tournament_id,
        f"organiser_id={user_id}",
    )
    db.commit()


@router.get("/audit-events")
def audit_events(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [
        {
            "id": event.id,
            "event": event.event,
            "success": event.success,
            "user_id": event.user_id,
            "target_id": event.target_id,
            "reason": event.reason,
            "created_at": event.created_at,
        }
        for event in db.query(AuthAuditEvent)
        .order_by(AuthAuditEvent.id.desc())
        .limit(100)
        .all()
    ]
