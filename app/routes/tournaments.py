from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.security import audit, current_user, financial_disabled, tournament_permission

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


@router.post("/", response_model=schemas.Tournament)
def create_tournament(
    tournament: schemas.TournamentCreate,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user.role not in ("organiser", "administrator"):
        raise HTTPException(403, "Organiser permission required")
    created = crud.create_tournament(db, tournament, commit=False)
    db.add(models.TournamentOrganiser(tournament_id=created.id, user_id=user.id))
    audit(db, "tournament_created", True, user.id, created.id)
    db.commit()
    return created


@router.get("/", response_model=list[schemas.Tournament])
def list_tournaments(
    user: models.User = Depends(current_user), db: Session = Depends(get_db)
):
    return crud.get_tournaments(db)


@router.post("/{tournament_id}/register")
def register_player(
    tournament_id: int,
    registration: schemas.TournamentRegistrationCreate,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if user.role != "administrator" and user.player_id != registration.player_id:
        tournament_permission(db, user, tournament_id)
    tournament = crud.get_tournament(db, tournament_id)
    if not tournament:
        raise HTTPException(404, "Tournament not found")
    if tournament.entry_fee != 0:
        financial_disabled()
    # No wallet call is reachable from this route until Task 04.
    result = crud.register_player(db, tournament_id, registration.player_id)
    audit(db, "player_registered", True, user.id, tournament_id)
    db.commit()
    return result


@router.post("/{tournament_id}/complete", response_model=list[schemas.TournamentResult])
def complete_tournament(
    tournament_id: int,
    winners: list[schemas.WinnerCreate],
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    tournament_permission(db, user, tournament_id)
    # Existing CRUD records standings/status only; it never distributes money.
    result = crud.complete_tournament(db, tournament_id, winners)
    audit(db, "tournament_completed", True, user.id, tournament_id)
    db.commit()
    return result
