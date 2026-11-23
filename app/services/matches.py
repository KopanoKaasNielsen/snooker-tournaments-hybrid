from sqlalchemy.orm import Session
from app.models import Match, Player
from app.tournament_v1_schema import require_legacy_tournament
from app.services.elo import update_elo_ratings


def update_match_result(db: Session, match_id: int, winner_id: int):
    match = db.get(Match, match_id)
    if not match:
        raise ValueError("Match not found")

    require_legacy_tournament(db, match.tournament_id)
    if match.winner_id:
        raise ValueError("Match result already set")

    if match.player1_id == winner_id:
        loser_id = match.player2_id
    elif match.player2_id == winner_id:
        loser_id = match.player1_id
    else:
        raise ValueError("Winner must be one of the players in the match")

    # Update Elo ratings
    winner = db.get(Player, winner_id)
    loser = db.get(Player, loser_id)

    winner.elo, loser.elo = update_elo_ratings(winner.elo, loser.elo)

    # Save match result
    match.winner_id = winner_id
    db.commit()
    return match
