import random
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from .. import models
from .elo import elo_update
from . import tournaments as svc_tournaments

from app.services.elo import update_elo_ratings
from app.models import Match, Player

def generate_knockout_draw(db: Session, tournament_id: int):
    regs = svc_tournaments.list_registrations(db, tournament_id)
    player_ids = [r.player_id for r in regs]
    random.shuffle(player_ids)

    if len(player_ids) % 2 == 1:
        player_ids.append(None)

    matches = []
    for i in range(0, len(player_ids), 2):
        p1, p2 = player_ids[i], player_ids[i+1]
        m = models.Match(tournament_id=tournament_id, round=1, player1_id=p1, player2_id=p2)
        if p1 and not p2:
            m.winner_id, m.completed, m.score1, m.score2 = p1, True, 1, 0
        if p2 and not p1:
            m.winner_id, m.completed, m.score1, m.score2 = p2, True, 0, 1
        db.add(m)
        matches.append(m)

    db.commit()
    return matches

def generate_league_schedule(db: Session, tournament_id: int):
    regs = svc_tournaments.list_registrations(db, tournament_id)
    player_ids = [r.player_id for r in regs]
    random.shuffle(player_ids)

    matches = []
    n = len(player_ids)
    for i in range(n):
        for j in range(i+1, n):
            m = models.Match(tournament_id=tournament_id, round=1,
                             player1_id=player_ids[i], player2_id=player_ids[j])
            db.add(m)
            matches.append(m)

    db.commit()
    return matches

def progress_knockout(db: Session, tournament_id: int):
    max_round = db.scalar(select(func.max(models.Match.round)).where(models.Match.tournament_id == tournament_id)) or 1
    total = db.scalar(select(func.count()).select_from(models.Match).where(models.Match.tournament_id == tournament_id, models.Match.round == max_round))
    completed = db.scalar(select(func.count()).select_from(models.Match).where(models.Match.tournament_id == tournament_id, models.Match.round == max_round, models.Match.completed == True))

    if completed < total:
        raise ValueError("Current round not complete")

    winners = list(db.scalars(select(models.Match.winner_id).where(models.Match.tournament_id == tournament_id, models.Match.round == max_round)))
    if len(winners) == 1:
        return []

    if len(winners) % 2 == 1:
        winners.append(None)

    next_round = max_round + 1
    new_matches = []
    for i in range(0, len(winners), 2):
        p1, p2 = winners[i], winners[i+1]
        m = models.Match(tournament_id=tournament_id, round=next_round, player1_id=p1, player2_id=p2)
        if p1 and not p2:
            m.winner_id, m.completed, m.score1, m.score2 = p1, True, 1, 0
        db.add(m)
        new_matches.append(m)

    db.commit()
    return new_matches

def list_matches(db: Session, tournament_id: int | None = None):
    stmt = select(models.Match)
    if tournament_id:
        stmt = stmt.where(models.Match.tournament_id == tournament_id)
    return list(db.scalars(stmt))

def set_result(db: Session, match_id: int, score1: int, score2: int):
    m = db.get(models.Match, match_id)
    if not m:
        raise ValueError("Match not found")
    if m.completed:
        return m

    m.score1, m.score2 = score1, score2
    if score1 == score2:
        raise ValueError("Draws not allowed")

    winner = m.player1_id if score1 > score2 else m.player2_id
    m.winner_id, m.completed = winner, True

    p1 = db.get(models.Player, m.player1_id) if m.player1_id else None
    p2 = db.get(models.Player, m.player2_id) if m.player2_id else None
    if p1 and p2:
        s1 = 1.0 if winner == p1.id else 0.0
        s2 = 1.0 - s1
        p1.rating, p2.rating = elo_update(p1.rating, p2.rating, s1, s2)

    db.commit()
    db.refresh(m)
    return m
def update_match_result(db: Session, match_id: int, winner_id: int):
    match = db.query(Match).get(match_id)
    if not match:
        raise ValueError("Match not found")

    if match.winner_id:
        raise ValueError("Match result already set")

    if match.player1_id == winner_id:
        loser_id = match.player2_id
    elif match.player2_id == winner_id:
        loser_id = match.player1_id
    else:
        raise ValueError("Winner must be one of the players in the match")

    # Update Elo ratings
    winner = db.query(Player).get(winner_id)
    loser = db.query(Player).get(loser_id)

    winner.elo, loser.elo = update_elo_ratings(winner.elo, loser.elo)

    # Save match result
    match.winner_id = winner_id
    db.commit()
    return matchclear
    