"""Pure domain services — financial and probabilistic calculations.

All functions in this module are pure (no side effects, no I/O) and operate
on primitive types. They form the computational core of the prediction-market
domain: implied probability, expected value, sizing, and calibration metrics.

See docs/math/ for detailed derivations and economic interpretation.
"""

from __future__ import annotations


def implied_probability(price: float, *, overround: float = 1.0) -> float:
    """Convert a market price to an implied probability.

    For a binary contract paying $1 on YES:
        implied_prob = price / overround

    Args:
        price: Observable market price in [0, 1].
        overround: Sum of all outcome prices. When > 1, the market has vig.
                   Dividing by overround normalizes to true probabilities.

    Raises:
        ValueError: If price is outside [0, 1].
    """
    if price < 0.0 or price > 1.0:
        msg = f"Price must be in [0, 1], got {price}"
        raise ValueError(msg)
    return price / overround


def expected_value(model_prob: float, cost: float, payout: float = 1.0) -> float:
    """Compute the expected value of a binary position.

    EV = model_prob * (payout - cost) - (1 - model_prob) * cost

    When payout=1, this simplifies to: EV = model_prob - cost.

    Args:
        model_prob: The model's estimated probability of YES.
        cost: The cost to enter the position.
        payout: The payout if YES resolves (default $1).
    """
    return model_prob * (payout - cost) - (1.0 - model_prob) * cost


def break_even_probability(cost: float, payout: float = 1.0) -> float:
    """Compute the minimum probability for non-negative EV.

    p_be = cost / payout

    A rational trader buys only if model_prob > p_be.
    """
    return cost / payout


def edge_bps(model_prob: float, market_prob: float) -> float:
    """Compute the edge in basis points.

    edge_bps = (model_prob - market_prob) * 10_000

    1 basis point = 0.01%.
    """
    return (model_prob - market_prob) * 10_000.0


def fractional_kelly(
    prob: float,
    odds: float,
    fraction: float = 0.25,
    max_fraction: float = 1.0,
) -> float:
    """Compute fractional Kelly bet size.

    Full Kelly for binary bets:
        f* = (p * b - q) / b

    where p = probability of winning, q = 1 - p, b = net odds.

    Fractional Kelly scales down to account for estimation uncertainty:
        f = fraction * f*

    The result is clamped to [0, max_fraction].

    Args:
        prob: Estimated probability of winning.
        odds: Net odds (payout / stake - 1). For even money, odds = 1.0.
        fraction: Kelly fraction (default 0.25, i.e. quarter Kelly).
        max_fraction: Maximum allowed bet as fraction of bankroll.

    Returns:
        Recommended bet size as a fraction of bankroll, in [0, max_fraction].
    """
    q = 1.0 - prob
    full_kelly = (prob * odds - q) / odds
    if full_kelly <= 0.0:
        return 0.0
    sized = fraction * full_kelly
    return min(sized, max_fraction)


def brier_score(forecasts: list[float], outcomes: list[float]) -> float:
    """Compute the Brier score for binary probabilistic forecasts.

    BS = (1/N) * Σ (forecast_i - outcome_i)²

    Properties:
    - BS = 0: perfect calibration.
    - BS = 1: worst possible (always wrong with max confidence).
    - BS = 0.25: no-skill baseline (always predict 0.5 on balanced data).

    Args:
        forecasts: Predicted probabilities, each in [0, 1].
        outcomes: Actual outcomes, each 0.0 or 1.0.

    Raises:
        ValueError: If inputs are empty or different lengths.
    """
    n = len(forecasts)
    if n == 0:
        msg = "Cannot compute Brier score on empty inputs"
        raise ValueError(msg)
    if n != len(outcomes):
        msg = f"forecasts length ({n}) != outcomes length ({len(outcomes)})"
        raise ValueError(msg)
    return sum((f - o) ** 2 for f, o in zip(forecasts, outcomes, strict=False)) / n
