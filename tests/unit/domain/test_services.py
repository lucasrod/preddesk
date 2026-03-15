"""Unit tests for domain services — pure financial/probabilistic calculations.

These tests serve a dual purpose:
1. Verify correctness of calculations.
2. Document the financial/probabilistic concepts with concrete examples.

Each test group includes a docstring explaining the underlying formula
and its economic interpretation.
"""

import pytest

from preddesk.domain.services import (
    break_even_probability,
    brier_score,
    edge_bps,
    expected_value,
    fractional_kelly,
    implied_probability,
)

# ---------------------------------------------------------------------------
# implied_probability
# ---------------------------------------------------------------------------


class TestImpliedProbability:
    """In a binary prediction market, the price of a YES contract directly
    implies the market's consensus probability.

    For a contract that pays $1 if YES and $0 if NO:
        implied_prob = price

    For the NO side:
        implied_prob(NO) = 1 - price(YES)

    Edge cases: price=0 means the market assigns 0% probability;
    price=1 means 100%.
    """

    def test_basic_conversion(self):
        assert implied_probability(0.65) == pytest.approx(0.65)

    def test_price_zero(self):
        assert implied_probability(0.0) == pytest.approx(0.0)

    def test_price_one(self):
        assert implied_probability(1.0) == pytest.approx(1.0)

    def test_with_overround(self):
        """When a market has overround (vig), the raw price overstates
        probability. Dividing by the overround normalizes it.

        Example: YES at 0.55, NO at 0.50 → overround = 1.05
        Normalized YES prob = 0.55 / 1.05 ≈ 0.5238
        """
        result = implied_probability(0.55, overround=1.05)
        assert result == pytest.approx(0.55 / 1.05, rel=1e-4)

    def test_rejects_negative_price(self):
        with pytest.raises(ValueError):
            implied_probability(-0.1)

    def test_rejects_price_above_one(self):
        with pytest.raises(ValueError):
            implied_probability(1.1)


# ---------------------------------------------------------------------------
# expected_value
# ---------------------------------------------------------------------------


class TestExpectedValue:
    """For a binary contract paying `payout` if correct at cost `cost`:

        EV = model_prob * (payout - cost) - (1 - model_prob) * cost

    Simplified when payout=1:
        EV = model_prob - cost

    EV > 0 signals a positive expected return under the model's estimate.
    """

    def test_positive_ev(self):
        """Model says 70% likely, market prices at 55 cents.
        EV = 0.70 * (1.0 - 0.55) - 0.30 * 0.55 = 0.315 - 0.165 = 0.15"""
        result = expected_value(model_prob=0.70, cost=0.55)
        assert result == pytest.approx(0.15)

    def test_negative_ev(self):
        """Model says 40% likely, market prices at 55 cents.
        EV = 0.40 - 0.55 = -0.15"""
        result = expected_value(model_prob=0.40, cost=0.55)
        assert result == pytest.approx(-0.15)

    def test_zero_ev_at_break_even(self):
        """When model_prob equals cost, EV is zero (assuming payout=1)."""
        result = expected_value(model_prob=0.60, cost=0.60)
        assert result == pytest.approx(0.0)

    def test_custom_payout(self):
        """For non-unit payouts:
        EV = 0.50 * (2.0 - 0.80) - 0.50 * 0.80 = 0.60 - 0.40 = 0.20"""
        result = expected_value(model_prob=0.50, cost=0.80, payout=2.0)
        assert result == pytest.approx(0.20)


# ---------------------------------------------------------------------------
# break_even_probability
# ---------------------------------------------------------------------------


class TestBreakEvenProbability:
    """Break-even probability is the minimum model probability needed for
    a trade to have non-negative expected value:

        p_be = cost / payout

    A trader should only buy if their model probability exceeds p_be.
    """

    def test_unit_payout(self):
        assert break_even_probability(cost=0.60) == pytest.approx(0.60)

    def test_custom_payout(self):
        assert break_even_probability(cost=0.60, payout=2.0) == pytest.approx(0.30)

    def test_free_contract(self):
        assert break_even_probability(cost=0.0) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# edge_bps
# ---------------------------------------------------------------------------


class TestEdgeBps:
    """Edge in basis points = (model_prob - market_prob) * 10_000.

    1 basis point = 0.01%. Expressing edge in bps is standard practice
    for comparing opportunities across markets with different price scales.
    """

    def test_positive_edge(self):
        result = edge_bps(model_prob=0.70, market_prob=0.55)
        assert result == pytest.approx(1500.0)

    def test_negative_edge(self):
        result = edge_bps(model_prob=0.40, market_prob=0.55)
        assert result == pytest.approx(-1500.0)

    def test_zero_edge(self):
        result = edge_bps(model_prob=0.55, market_prob=0.55)
        assert result == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# fractional_kelly
# ---------------------------------------------------------------------------


class TestFractionalKelly:
    """The Kelly criterion maximizes the expected logarithmic growth rate
    of capital. For a binary bet:

        f* = (p * b - q) / b

    where p = win probability, q = 1 - p, b = net odds (payout/cost - 1).

    Full Kelly is too aggressive when probability estimates are uncertain,
    so we use a fraction (default 0.25) of the full Kelly:

        f_fractional = fraction * f*

    The output is clamped to [0, max_fraction] to prevent over-betting.
    """

    def test_positive_edge_returns_size(self):
        """Model prob 0.70, odds of 1.0 (even money, cost=0.50, payout=1.0).
        Full Kelly = (0.70 * 1.0 - 0.30) / 1.0 = 0.40
        Fractional (0.25): 0.10"""
        result = fractional_kelly(prob=0.70, odds=1.0, fraction=0.25)
        assert result == pytest.approx(0.10)

    def test_no_edge_returns_zero(self):
        """When prob equals implied break-even, Kelly says don't bet."""
        result = fractional_kelly(prob=0.50, odds=1.0)
        assert result == pytest.approx(0.0)

    def test_negative_edge_returns_zero(self):
        """Kelly never recommends a negative bet size."""
        result = fractional_kelly(prob=0.30, odds=1.0)
        assert result == pytest.approx(0.0)

    def test_respects_fraction(self):
        """Higher fraction → larger bet size, but still capped."""
        quarter = fractional_kelly(prob=0.80, odds=1.0, fraction=0.25)
        half = fractional_kelly(prob=0.80, odds=1.0, fraction=0.50)
        assert half > quarter

    def test_respects_max_fraction(self):
        """Even with extreme edge, position size is capped."""
        result = fractional_kelly(prob=0.99, odds=1.0, fraction=1.0, max_fraction=0.20)
        assert result <= 0.20

    def test_full_kelly_not_default(self):
        """Spec requirement: full Kelly is never the default."""
        result = fractional_kelly(prob=0.80, odds=1.0)
        full_kelly = (0.80 * 1.0 - 0.20) / 1.0
        assert result < full_kelly


# ---------------------------------------------------------------------------
# brier_score
# ---------------------------------------------------------------------------


class TestBrierScore:
    """The Brier score measures the accuracy of probabilistic forecasts:

        BS = (1/N) * Σ(forecast_i - outcome_i)²

    where outcome_i ∈ {0, 1}.

    Properties:
    - Perfect forecasts: BS = 0 (best).
    - Worst possible: BS = 1 (always predict 1.0 for events that don't happen).
    - Uniform 0.5 forecasts on balanced data: BS = 0.25.
    """

    def test_perfect_forecasts(self):
        forecasts = [1.0, 0.0, 1.0]
        outcomes = [1.0, 0.0, 1.0]
        assert brier_score(forecasts, outcomes) == pytest.approx(0.0)

    def test_worst_forecasts(self):
        forecasts = [1.0, 1.0, 1.0]
        outcomes = [0.0, 0.0, 0.0]
        assert brier_score(forecasts, outcomes) == pytest.approx(1.0)

    def test_uniform_forecasts(self):
        """Predicting 0.5 for everything on balanced outcomes → BS = 0.25."""
        forecasts = [0.5, 0.5]
        outcomes = [1.0, 0.0]
        assert brier_score(forecasts, outcomes) == pytest.approx(0.25)

    def test_intermediate(self):
        """Forecast 0.8 for an event that happens: (0.8 - 1.0)² = 0.04."""
        forecasts = [0.8]
        outcomes = [1.0]
        assert brier_score(forecasts, outcomes) == pytest.approx(0.04)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            brier_score([], [])

    def test_mismatched_lengths_raises(self):
        with pytest.raises(ValueError):
            brier_score([0.5], [1.0, 0.0])
