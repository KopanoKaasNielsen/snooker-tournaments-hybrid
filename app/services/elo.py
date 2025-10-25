def expected_score(player_rating: float, opponent_rating: float) -> float:
    return 1 / (1 + 10 ** ((opponent_rating - player_rating) / 400))


def update_elo_ratings(winner_rating: float, loser_rating: float, k: int = 40) -> tuple[int, int]:
    expected_win = expected_score(winner_rating, loser_rating)
    expected_loss = expected_score(loser_rating, winner_rating)

    new_winner = round(winner_rating + k * (1 - expected_win))
    new_loser = round(loser_rating + k * (0 - expected_loss))

    return new_winner, new_loser


def elo_update(r_a: float, r_b: float, score_a: float, score_b: float, k: float = 40.0):
    exp_a = 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))
    exp_b = 1.0 / (1.0 + 10 ** ((r_a - r_b) / 400.0))
    return r_a + k * (score_a - exp_a), r_b + k * (score_b - exp_b)





