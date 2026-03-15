"""Property-based tests for value objects using Hypothesis.

These tests verify invariants that must hold for *all* valid inputs,
not just hand-picked examples. Hypothesis generates hundreds of random
test cases, making it much harder for edge cases to slip through.
"""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from preddesk.domain.value_objects import (
    ConfidenceInterval,
    Percentage,
    Price,
    Probability,
    Quantity,
    TimeRange,
)

# ---------------------------------------------------------------------------
# Probability
# ---------------------------------------------------------------------------


class TestProbabilityProperties:
    """Probability invariant: value ∈ [0, 1] for all valid instances."""

    @given(v=st.floats(min_value=0.0, max_value=1.0, allow_nan=False))
    def test_always_in_unit_interval(self, v: float):
        p = Probability(value=v)
        assert 0.0 <= p.value <= 1.0

    @given(v=st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False))
    def test_rejects_all_negatives(self, v: float):
        with pytest.raises(ValueError):
            Probability(value=v)

    @given(v=st.floats(min_value=1.001, allow_nan=False, allow_infinity=False))
    def test_rejects_all_above_one(self, v: float):
        with pytest.raises(ValueError):
            Probability(value=v)


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------


class TestPriceProperties:
    """Price invariant: value >= 0 for all valid instances."""

    @given(v=st.floats(min_value=0.0, max_value=1e6, allow_nan=False))
    def test_always_non_negative(self, v: float):
        p = Price(value=v)
        assert p.value >= 0.0

    @given(v=st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False))
    def test_rejects_all_negatives(self, v: float):
        with pytest.raises(ValueError):
            Price(value=v)


# ---------------------------------------------------------------------------
# Quantity
# ---------------------------------------------------------------------------


class TestQuantityProperties:
    """Quantity invariants: value >= 0, not NaN, not Inf."""

    @given(v=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False))
    def test_always_non_negative_and_finite(self, v: float):
        q = Quantity(value=v)
        assert q.value >= 0.0
        import math

        assert not math.isnan(q.value)
        assert not math.isinf(q.value)

    @given(v=st.floats(max_value=-0.001, allow_nan=False, allow_infinity=False))
    def test_rejects_all_negatives(self, v: float):
        with pytest.raises(ValueError):
            Quantity(value=v)


# ---------------------------------------------------------------------------
# ConfidenceInterval
# ---------------------------------------------------------------------------


class TestConfidenceIntervalProperties:
    """CI invariants: 0 <= lower <= upper <= 1."""

    @given(
        lower=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        upper=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    def test_valid_intervals_maintain_invariant(self, lower: float, upper: float):
        assume(lower <= upper)
        ci = ConfidenceInterval(lower=lower, upper=upper)
        assert 0.0 <= ci.lower <= ci.upper <= 1.0

    @given(
        lower=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
        upper=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    def test_width_is_non_negative(self, lower: float, upper: float):
        assume(lower <= upper)
        ci = ConfidenceInterval(lower=lower, upper=upper)
        assert ci.width >= 0.0


# ---------------------------------------------------------------------------
# TimeRange
# ---------------------------------------------------------------------------


class TestTimeRangeProperties:
    @given(
        offset_hours=st.integers(min_value=0, max_value=8760),
        duration_hours=st.integers(min_value=0, max_value=8760),
    )
    def test_start_always_leq_end(self, offset_hours: int, duration_hours: int):
        base = datetime(2025, 1, 1, tzinfo=UTC)
        start = base + timedelta(hours=offset_hours)
        end = start + timedelta(hours=duration_hours)
        tr = TimeRange(start=start, end=end)
        assert tr.start <= tr.end


# ---------------------------------------------------------------------------
# Percentage
# ---------------------------------------------------------------------------


class TestPercentageProperties:
    @given(v=st.floats(allow_nan=False, allow_infinity=False))
    def test_accepts_all_finite_values(self, v: float):
        p = Percentage(value=v)
        import math

        assert math.isfinite(p.value)
