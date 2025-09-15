def elo_update(r_a: float, r_b: float, score_a: float, score_b: float, k: float = 32.0):
    exp_a = 1.0 / (1.0 + 10 ** ((r_b - r_a) / 400.0))
    exp_b = 1.0 / (1.0 + 10 ** ((r_a - r_b) / 400.0))
    return r_a + k * (score_a - exp_a), r_b + k * (score_b - exp_b)
