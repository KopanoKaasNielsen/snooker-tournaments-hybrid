from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.database import get_db
from app.security import audit, current_user, tournament_permission

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("/", response_model=schemas.Match)
def create_match(
    match: schemas.MatchCreate,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    tournament_permission(db, user, match.tournament_id)
    return crud.create_match(db, match)


@router.get("/", response_model=list[schemas.Match])
def list_matches(
    user: models.User = Depends(current_user), db: Session = Depends(get_db)
):
    return crud.get_matches(db)


@router.post("/{match_id}/result", response_model=schemas.Match)
def report_result(
    match_id: int,
    result: schemas.MatchResult,
    user: models.User = Depends(current_user),
    db: Session = Depends(get_db),
):
    match = db.get(models.Match, match_id)
    if not match:
        raise HTTPException(404, "Match not found")
    tournament_permission(db, user, match.tournament_id)
    updated = crud.report_result(db, match_id, result)
    audit(db, "match_result_submitted", True, user.id, match_id)
    db.commit()
    return updated
