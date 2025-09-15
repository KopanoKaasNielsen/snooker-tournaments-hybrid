# app/routes/tournaments.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app import schemas, models, crud
from app.database import get_db
from app.services import tournaments as tournament_service
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import models, schemas

router = APIRouter(prefix="/tournaments", tags=["tournaments"])


# Register a player to a tournament
def register_player(db: Session, tournament_id: int, player_data: schemas.RegisterPlayer):
    tournament = db.query(models.Tournament).filter(models.Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    # Check if player exists
    player = db.query(models.Player).filter(models.Player.id == player_data.player_id).first()
    if not player:
        # Create new player
        player = models.Player(id=player_data.player_id, name=player_data.name)
        db.add(player)
        db.commit()
        db.refresh(player)

    # Check if already registered
    existing = (
        db.query(models.PlayerTournament)
        .filter(
            models.PlayerTournament.tournament_id == tournament_id,
            models.PlayerTournament.player_id == player.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Player {player.name} is already registered for this tournament")

    # Register
    reg = models.PlayerTournament(player_id=player.id, tournament_id=tournament_id)
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg


# Distribute prizes
@router.post("/{tournament_id}/prizes/distribute")
def distribute_prizes(
    tournament_id: int,
    winners: list[int],  # expects: [1st_id, 2nd_id, 3rd_id, 4th_id]
    db: Session = Depends(get_db),
):
    tournament_service.distribute_prizes(db, tournament_id, winners)
    return {"status": "success", "tournament_id": tournament_id}


# Cancel tournament
@router.post("/{tournament_id}/cancel")
def cancel_tournament(
    tournament_id: int,
    db: Session = Depends(get_db),
):
    tournament_service.cancel_tournament(db, tournament_id)
    return {"status": "cancelled", "tournament_id": tournament_id}
