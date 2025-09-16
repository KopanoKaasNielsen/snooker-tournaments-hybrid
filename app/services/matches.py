from sqlalchemy.orm import Session
from app.models import Match, Player
from app.services.elo import update_elo_ratings


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
    return match
