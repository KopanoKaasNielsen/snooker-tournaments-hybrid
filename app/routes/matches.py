from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app import crud, schemas
from app.database import get_db
from datetime import datetime

router = APIRouter(prefix='/matches', tags=['matches'])

@router.post("/", response_model=schemas.Match)
def create_match(match: schemas.MatchCreate, db: Session = Depends(get_db)):
    return crud.create_match(db, match)

@router.get('/', response_model=list[schemas.Match])
def list_matches(db: Session = Depends(get_db)):
    return crud.get_matches(db)



@router.post("/{match_id}/result", response_model=schemas.Match)
def report_result(
    match_id: int,
    result: schemas.MatchResult,
    db: Session = Depends(get_db),
):
    return crud.report_result(db, match_id, result)
