import random
from sqlalchemy.orm import Session
from fastapi import HTTPException
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


def register_player(db: Session, tournament_id: int, player_id: int):
    """
    Register an existing player to a tournament.
    Assumes player already exists (no name creation fallback).
    """
    tournament = db.query(Tournament).filter(Tournament.id == tournament_id).first()
    if not tournament:
        raise HTTPException(status_code=404, detail="Tournament not found")

    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    existing = db.query(TournamentRegistration).filter_by(
        tournament_id=tournament_id, player_id=player_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Player already registered")

    reg = TournamentRegistration(player_id=player_id, tournament_id=tournament_id)
    db.add(reg)
    db.commit()
    db.refresh(reg)
    return reg
