"""Property-based tests for pricing and financial calculation invariants.

These tests verify mathematical properties that must hold for all valid
inputs to the domain services: implied probability, expected value,
Kelly sizing, and edge calculations.
"""

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from preddesk.domain.services import (
    break_even_probability,
    edge_bps,
    expected_value,
    fractional_kelly,
    implied_probability,
)

# ---------------------------------------------------------------------------
# Implied probability
# ---------------------------------------------------------------------------


class TestImpliedProbabilityProperties:
    @given(
        price=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    )
    def test_output_is_valid_probability(self, price):
        """Implied probability is always in [0, 1] for valid prices."""
        p = implied_probability(price)
        assert 0.0 <= p <= 1.0

    @given(
        p1=st.floats(min_value=0.01, max_value=0.98, allow_nan=False, allow_infinity=False),
        delta=st.floats(min_value=0.001, max_value=0.01, allow_nan=False, allow_infinity=False),
    )
    def test_monotonically_increasing(self, p1, delta):
        """Higher price implies higher probability (with overround=1.0)."""
        p2 = p1 + delta
        assume(p2 <= 0.99)
        assert implied_probability(p2) >= implied_probability(p1)


# ---------------------------------------------------------------------------
# Expected value
# ---------------------------------------------------------------------------


class TestExpectedValueProperties:
    @given(
        model_prob=st.floats(
            min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False
        ),
        cost=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    )
    def test_ev_positive_when_prob_exceeds_cost(self, model_prob, cost):
        """EV = p - c for a unit-payout binary contract (no fees).

        When model_prob > cost, EV is positive (edge exists).
        """
        ev = expected_value(model_prob, cost)
        if model_prob > cost:
            assert ev > 0.0
        elif model_prob < cost:
            assert ev < 0.0

    @given(
        cost=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    )
    def test_ev_zero_at_break_even(self, cost):
        """EV is zero when model_prob equals break-even probability."""
        be = break_even_probability(cost)
        ev = expected_value(be, cost)
        assert ev == pytest.approx(0.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Edge in basis points
# ---------------------------------------------------------------------------


class TestEdgeBpsProperties:
    @given(
        model=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        market=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_edge_is_antisymmetric(self, model, market):
        """edge(a, b) = -edge(b, a)."""
        e1 = edge_bps(model, market)
        e2 = edge_bps(market, model)
        assert e1 == pytest.approx(-e2, abs=1e-6)

    @given(
        prob=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_zero_edge_when_equal(self, prob):
        """No edge when model and market agree."""
        assert edge_bps(prob, prob) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Fractional Kelly
# ---------------------------------------------------------------------------


class TestKellyProperties:
    @given(
        prob=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
        odds=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
        fraction=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_kelly_never_negative(self, prob, odds, fraction):
        """Kelly sizing is always >= 0 (no shorting in this model)."""
        k = fractional_kelly(prob, odds, fraction=fraction)
        assert k >= 0.0

    @given(
        prob=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
        odds=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
        fraction=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_kelly_bounded_by_max_fraction(self, prob, odds, fraction):
        """Kelly bet size never exceeds the max_fraction cap."""
        k = fractional_kelly(prob, odds, fraction=fraction, max_fraction=1.0)
        assert k <= 1.0

    @given(
        prob=st.floats(min_value=0.01, max_value=0.49, allow_nan=False, allow_infinity=False),
    )
    def test_kelly_zero_for_negative_edge(self, prob):
        """When probability is below break-even at even odds, Kelly returns 0."""
        # At even odds (1:1), break-even is 0.50
        k = fractional_kelly(prob, odds=1.0)
        assert k == pytest.approx(0.0)
