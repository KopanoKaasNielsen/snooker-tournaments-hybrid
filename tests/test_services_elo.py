from app.services.elo import update_elo_ratings


def test_elo_update_basic():
    winner, loser = update_elo_ratings(1500, 1500)
    assert winner > 1500
    assert loser < 1500
    assert (winner - 1500) == (1500 - loser)


def test_elo_underdog_wins():
    winner, loser = update_elo_ratings(1300, 1700)
    assert winner > 1300 + 30  # big underdog win
    assert loser < 1700 - 30


def test_elo_favorite_wins():
    winner, loser = update_elo_ratings(1700, 1300)
    assert winner < 1700 + 10  # expected outcome, small change
    assert loser > 1300 - 10
