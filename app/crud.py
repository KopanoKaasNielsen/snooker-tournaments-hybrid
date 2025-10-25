from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List
from . import models, schemas
from datetime import datetime

def create_player(db: Session, player: schemas.PlayerCreate):
    existing = db.query(models.Player).filter(models.Player.name == player.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Player '{player.name}' already exists")
    db_player = models.Player(name=player.name, rating=player.rating)
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player

def get_players(db: Session):
    return db.query(models.Player).all()

def get_player(db: Session, player_id: int):
    p = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not p:
        raise HTTPException(status_code=404, detail='Player not found')
    return p

def create_tournament(db: Session, tournament: schemas.TournamentCreate):
    existing = db.query(models.Tournament).filter(models.Tournament.name == tournament.name).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"A tournament named '{tournament.name}' already exists.")
    # normalize type string to enum-like value (models expect enum names values at DB layer)
    tournament_date = tournament.date
    if isinstance(tournament_date, str):
        tournament_date = datetime.fromisoformat(tournament_date)

    t = models.Tournament(
        name=tournament.name,
        type=tournament.type,
        date=tournament_date,
        best_of=tournament.best_of,
        race_to=tournament.race_to,
        entry_fee=tournament.entry_fee,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t

def get_tournaments(db: Session):
    return db.query(models.Tournament).all()


def get_tournament(db: Session, tournament_id: int):
    return db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()

def register_player(db: Session, tournament_id: int, player_id: int, player_name: str | None = None):
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail='Tournament not found')
    # ensure player exists (create if player_name provided)
    player = db.query(models.Player).filter(models.Player.id == player_id).first()
    if not player:
        if not player_name:
            raise HTTPException(status_code=404, detail=f'Player {player_id} not found; provide name to create.')
        player = models.Player(name=player_name, rating=1500)
        db.add(player)
        db.commit()
        db.refresh(player)

    existing = db.query(models.TournamentRegistration).filter_by(tournament_id=tournament_id, player_id=player.id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f'Player {player.name} is already registered for this tournament.')
    reg = models.TournamentRegistration(tournament_id=tournament_id, player_id=player.id)
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg

def complete_tournament(db: Session, tournament_id: int, winners: List[schemas.WinnerCreate]):
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail='Tournament not found')
    if tournament.status.value == 'COMPLETED':
        raise HTTPException(status_code=400, detail='Tournament already completed')
    # validations
    positions = [w.position for w in winners]
    if len(positions) != len(set(positions)):
        raise HTTPException(status_code=400, detail='Duplicate positions detected')
    if any(p < 1 or p > 4 for p in positions):
        raise HTTPException(status_code=400, detail='Positions must be between 1 and 4')
    registered_ids = {r.player_id for r in tournament.registrations}
    for w in winners:
        if w.player_id not in registered_ids:
            raise HTTPException(status_code=400, detail=f'Player {w.player_id} is not registered in this tournament')
    # create results
    results = []
    for w in winners:
        res = models.TournamentResult(tournament_id=tournament_id, player_id=w.player_id, position=w.position)
        db.add(res)
        results.append(res)
    tournament.status = models.TournamentStatus.COMPLETED
    db.commit()
    for r in results:
        db.refresh(r)
    return results

def create_match(db: Session, match: schemas.MatchCreate):
    db_match = models.Match(
        tournament_id=match.tournament_id,
        player1_id=match.player1_id,
        player2_id=match.player2_id,
        scheduled_at=match.scheduled_at,
        score_player1=0,
        score_player2=0,
        winner_id=None,
    )
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    return db_match


def report_result(db: Session, match_id: int, result: schemas.MatchResult):
    db_match = db.query(models.Match).filter(models.Match.id == match_id).first()
    if not db_match:
        raise HTTPException(status_code=404, detail="Match not found")

    # Update match result
    db_match.score_player1 = result.score_player1
    db_match.score_player2 = result.score_player2
    db_match.winner_id = result.winner_id
    db_match.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(db_match)

    # Check if all matches in the tournament are complete
    tournament = db.query(models.Tournament).filter(models.Tournament.id == db_match.tournament_id).first()
    if tournament:
        matches = db.query(models.Match).filter(models.Match.tournament_id == tournament.id).all()
        if all(m.winner_id is not None for m in matches):  # all matches finished
            tournament.status = "COMPLETED"
            db.commit()
            db.refresh(tournament)

    return db_match

def get_matches(db: Session):
    """Return all matches from the database."""
    return db.query(models.Match).all()

