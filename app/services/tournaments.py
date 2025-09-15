import random
from sqlalchemy.orm import Session
from app.models import Tournament, Match, Player, TournamentRegistration


def distribute_prizes(db: Session, tournament: Tournament, prize_split=(1.0,)):
    """
    Distribute prize pool among top finishers.
    Default: 100% to winner.
    """
    prize_pool = tournament.entry_fee * len(tournament.registrations)
    winners = tournament.final_standings or []

    if not winners:
        raise ValueError("No final standings provided for prize distribution.")

    # Limit prize split to number of winners
    split = prize_split[:len(winners)]

    for i, player_id in enumerate(winners):
        share = split[i] if i < len(split) else 0
        prize = round(prize_pool * share, 2)
        player = db.query(Player).get(player_id)
        if player:
            player.balance += prize

    db.commit()


def generate_knockout_matches(db: Session, tournament: Tournament):
    """
    Generate first-round knockout matches.
    Handles byes for odd player counts.
    """
    players = [r.player for r in tournament.registrations]
    if len(players) < 2:
        return []

    random.shuffle(players)
    matches = []

    while len(players) >= 2:
        p1 = players.pop()
        p2 = players.pop()
        match = Match(
            tournament_id=tournament.id,
            player1_id=p1.id,
            player2_id=p2.id,
            scheduled_at=tournament.date,
        )
        db.add(match)
        matches.append(match)

    # Handle bye (odd number of players)
    if players:
        bye_player = players.pop()
        auto_win = Match(
            tournament_id=tournament.id,
            player1_id=bye_player.id,
            player2_id=None,
            winner_id=bye_player.id,
            scheduled_at=tournament.date,
        )
        db.add(auto_win)
        matches.append(auto_win)

    db.commit()
    return matches
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
