"""Unit tests for domain value objects.

These tests verify the fundamental invariants that protect the system
from invalid states at the lowest level. Every number that flows through
the domain — probabilities, prices, quantities — must satisfy strict
constraints. Catching violations here prevents silent corruption downstream.
"""

from datetime import UTC
from decimal import Decimal

import pytest
from pydantic import ValidationError

from preddesk.domain.value_objects import (
    ConfidenceInterval,
    MarketProbabilitySpread,
    MarketSide,
    Money,
    OrderSide,
    Percentage,
    Price,
    Probability,
    Quantity,
    TimeRange,
)

# ---------------------------------------------------------------------------
# Probability
# ---------------------------------------------------------------------------


class TestProbability:
    """A probability must live in [0, 1]. This is the most fundamental
    invariant in a prediction-market system: every implied price, model
    estimate, and posterior is a probability."""

    def test_valid_interior_value(self):
        p = Probability(value=0.65)
        assert p.value == pytest.approx(0.65)

    def test_accepts_zero(self):
        assert Probability(value=0.0).value == 0.0

    def test_accepts_one(self):
        assert Probability(value=1.0).value == 1.0

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            Probability(value=-0.01)

    def test_rejects_greater_than_one(self):
        with pytest.raises(ValueError):
            Probability(value=1.001)

    def test_immutable(self):
        p = Probability(value=0.5)
        with pytest.raises(ValidationError):
            p.value = 0.9  # type: ignore[misc]

    def test_equality(self):
        assert Probability(value=0.5) == Probability(value=0.5)

    def test_inequality(self):
        assert Probability(value=0.5) != Probability(value=0.6)


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------


class TestPrice:
    """In prediction markets, prices represent the cost of a contract and
    are non-negative. A contract priced at 0.60 means paying $0.60 for a
    potential $1.00 payout."""

    def test_valid_price(self):
        assert Price(value=0.60).value == pytest.approx(0.60)

    def test_accepts_zero(self):
        assert Price(value=0.0).value == 0.0

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            Price(value=-0.01)

    def test_immutable(self):
        p = Price(value=1.0)
        with pytest.raises(ValidationError):
            p.value = 2.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------


class TestMoney:
    """Money is a Decimal amount with an explicit currency. Using Decimal
    avoids floating-point rounding errors that would corrupt PnL tracking."""

    def test_creation(self):
        m = Money(amount=Decimal("100.50"), currency="USD")
        assert m.amount == Decimal("100.50")
        assert m.currency == "USD"

    def test_default_currency(self):
        m = Money(amount=Decimal("10"))
        assert m.currency == "USD"

    def test_immutable(self):
        m = Money(amount=Decimal("10"))
        with pytest.raises(ValidationError):
            m.amount = Decimal("20")  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Quantity
# ---------------------------------------------------------------------------


class TestQuantity:
    """Quantity of contracts. Must be non-negative and finite — NaN or Inf
    would silently corrupt position and PnL calculations."""

    def test_valid_quantity(self):
        assert Quantity(value=10.0).value == 10.0

    def test_accepts_zero(self):
        assert Quantity(value=0.0).value == 0.0

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            Quantity(value=-1.0)

    def test_rejects_nan(self):
        with pytest.raises(ValueError):
            Quantity(value=float("nan"))

    def test_rejects_inf(self):
        with pytest.raises(ValueError):
            Quantity(value=float("inf"))


# ---------------------------------------------------------------------------
# Percentage
# ---------------------------------------------------------------------------


class TestPercentage:
    """Percentage is unconstrained in range (can be negative for losses)
    but must be finite."""

    def test_positive(self):
        assert Percentage(value=15.5).value == pytest.approx(15.5)

    def test_negative(self):
        assert Percentage(value=-3.2).value == pytest.approx(-3.2)

    def test_rejects_nan(self):
        with pytest.raises(ValueError):
            Percentage(value=float("nan"))

    def test_rejects_inf(self):
        with pytest.raises(ValueError):
            Percentage(value=float("inf"))


# ---------------------------------------------------------------------------
# TimeRange
# ---------------------------------------------------------------------------


class TestTimeRange:
    """A time range with start <= end, used for event windows and
    backtest periods."""

    def test_valid_range(self):
        from datetime import datetime

        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 6, 1, tzinfo=UTC)
        tr = TimeRange(start=start, end=end)
        assert tr.start == start
        assert tr.end == end

    def test_same_start_end(self):
        from datetime import datetime

        t = datetime(2025, 1, 1, tzinfo=UTC)
        tr = TimeRange(start=t, end=t)
        assert tr.start == tr.end

    def test_rejects_start_after_end(self):
        from datetime import datetime

        with pytest.raises(ValueError):
            TimeRange(
                start=datetime(2025, 6, 1, tzinfo=UTC),
                end=datetime(2025, 1, 1, tzinfo=UTC),
            )


# ---------------------------------------------------------------------------
# ConfidenceInterval
# ---------------------------------------------------------------------------


class TestConfidenceInterval:
    """Confidence interval for probability estimates. Both bounds must be
    valid probabilities and lower <= upper."""

    def test_valid_interval(self):
        ci = ConfidenceInterval(lower=0.3, upper=0.7)
        assert ci.lower == pytest.approx(0.3)
        assert ci.upper == pytest.approx(0.7)

    def test_point_estimate(self):
        ci = ConfidenceInterval(lower=0.5, upper=0.5)
        assert ci.lower == ci.upper

    def test_rejects_lower_greater_than_upper(self):
        with pytest.raises(ValueError):
            ConfidenceInterval(lower=0.8, upper=0.3)

    def test_rejects_bounds_outside_zero_one(self):
        with pytest.raises(ValueError):
            ConfidenceInterval(lower=-0.1, upper=0.5)
        with pytest.raises(ValueError):
            ConfidenceInterval(lower=0.5, upper=1.1)

    def test_width(self):
        ci = ConfidenceInterval(lower=0.2, upper=0.8)
        assert ci.width == pytest.approx(0.6)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestMarketSide:
    def test_values(self):
        assert MarketSide.YES.value == "YES"
        assert MarketSide.NO.value == "NO"


class TestOrderSide:
    def test_values(self):
        assert OrderSide.BUY.value == "BUY"
        assert OrderSide.SELL.value == "SELL"


# ---------------------------------------------------------------------------
# MarketProbabilitySpread
# ---------------------------------------------------------------------------


class TestMarketProbabilitySpread:
    """The spread between model probability and market probability captures
    the perceived edge. edge_bps = (model_prob - market_prob) * 10_000."""

    def test_creation(self):
        s = MarketProbabilitySpread(model_probability=0.70, market_probability=0.55)
        assert s.model_probability == 0.70
        assert s.market_probability == 0.55

    def test_edge_bps(self):
        s = MarketProbabilitySpread(model_probability=0.70, market_probability=0.55)
        assert s.edge_bps == pytest.approx(1500.0)

    def test_negative_edge(self):
        s = MarketProbabilitySpread(model_probability=0.40, market_probability=0.55)
        assert s.edge_bps == pytest.approx(-1500.0)

    def test_has_positive_edge(self):
        pos = MarketProbabilitySpread(model_probability=0.70, market_probability=0.55)
        neg = MarketProbabilitySpread(model_probability=0.40, market_probability=0.55)
        assert pos.has_positive_edge is True
        assert neg.has_positive_edge is False

    def test_rejects_invalid_model_probability(self):
        with pytest.raises(ValidationError):
            MarketProbabilitySpread(model_probability=1.5, market_probability=0.5)

    def test_rejects_invalid_market_probability(self):
        with pytest.raises(ValidationError):
            MarketProbabilitySpread(model_probability=0.5, market_probability=-0.1)

    def test_immutable(self):
        s = MarketProbabilitySpread(model_probability=0.70, market_probability=0.55)
        with pytest.raises(ValidationError):
            s.model_probability = 0.80
