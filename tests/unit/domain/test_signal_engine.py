"""Unit tests for the signal engine.

Signals transform differences between market price and model probability
into actionable, scored opportunities. Every signal must be:
1. Pure — no side effects, no I/O.
2. Explainable — produces a rationale string.
3. Testable — deterministic given inputs.

Signal types tested:
- ProbabilityGapSignal: raw difference in probability.
- EVSignal: expected value of a hypothetical position.
- ThresholdSignal: binary alert when edge exceeds a threshold.
- ConfidenceWeightedSignal: reduces score when model uncertainty is high.
"""

import pytest

from preddesk.domain.signal_engine import (
    ConfidenceWeightedSignal,
    EVSignal,
    ProbabilityGapSignal,
    SignalResult,
    ThresholdSignal,
    rank_signals,
)

# ---------------------------------------------------------------------------
# ProbabilityGapSignal
# ---------------------------------------------------------------------------


class TestProbabilityGapSignal:
    """The simplest signal: model_prob - market_prob.

    Edge in basis points = (model_prob - market_prob) * 10_000.
    A positive edge means the model thinks the market is underpriced.
    """

    def test_positive_edge(self):
        sig = ProbabilityGapSignal()
        result = sig.evaluate(model_prob=0.70, market_prob=0.55)
        assert result.edge_bps == pytest.approx(1500.0)
        assert result.is_actionable is True

    def test_negative_edge(self):
        sig = ProbabilityGapSignal()
        result = sig.evaluate(model_prob=0.40, market_prob=0.55)
        assert result.edge_bps == pytest.approx(-1500.0)
        assert result.is_actionable is False

    def test_zero_edge(self):
        sig = ProbabilityGapSignal()
        result = sig.evaluate(model_prob=0.55, market_prob=0.55)
        assert result.edge_bps == pytest.approx(0.0)
        assert result.is_actionable is False

    def test_has_rationale(self):
        sig = ProbabilityGapSignal()
        result = sig.evaluate(model_prob=0.70, market_prob=0.55)
        assert "1500" in result.rationale
        assert result.signal_type == "probability_gap"


# ---------------------------------------------------------------------------
# EVSignal
# ---------------------------------------------------------------------------


class TestEVSignal:
    """EV signal computes expected value for a YES position:

        EV = model_prob * (payout - cost) - (1 - model_prob) * cost

    where cost ≈ market_prob for a unit-payout contract.
    Fees shift the break-even point upward.
    """

    def test_positive_ev(self):
        sig = EVSignal()
        result = sig.evaluate(model_prob=0.70, market_prob=0.55)
        # EV = 0.70 - 0.55 = 0.15
        assert result.expected_value == pytest.approx(0.15)
        assert result.is_actionable is True

    def test_negative_ev(self):
        sig = EVSignal()
        result = sig.evaluate(model_prob=0.40, market_prob=0.55)
        assert result.expected_value == pytest.approx(-0.15)
        assert result.is_actionable is False

    def test_with_fees(self):
        """Fees increase effective cost, reducing EV.
        Effective cost = market_prob + fee_rate.
        EV = model_prob - (market_prob + fee_rate)
        = 0.70 - (0.55 + 0.02) = 0.13
        """
        sig = EVSignal(fee_rate=0.02)
        result = sig.evaluate(model_prob=0.70, market_prob=0.55)
        assert result.expected_value == pytest.approx(0.13)

    def test_fees_can_flip_signal(self):
        """A barely positive edge can become negative after fees."""
        sig = EVSignal(fee_rate=0.05)
        result = sig.evaluate(model_prob=0.58, market_prob=0.55)
        # EV = 0.58 - (0.55 + 0.05) = -0.02
        assert result.expected_value < 0.0
        assert result.is_actionable is False

    def test_has_rationale(self):
        sig = EVSignal()
        result = sig.evaluate(model_prob=0.70, market_prob=0.55)
        assert result.signal_type == "expected_value"


# ---------------------------------------------------------------------------
# ThresholdSignal
# ---------------------------------------------------------------------------


class TestThresholdSignal:
    """Fires only when edge exceeds a configurable threshold in basis points.

    This avoids noise from tiny mispricings that wouldn't survive
    transaction costs.
    """

    def test_above_threshold(self):
        sig = ThresholdSignal(threshold_bps=500.0)
        result = sig.evaluate(model_prob=0.70, market_prob=0.55)
        # edge = 1500 bps > 500 threshold
        assert result.is_actionable is True

    def test_below_threshold(self):
        sig = ThresholdSignal(threshold_bps=2000.0)
        result = sig.evaluate(model_prob=0.70, market_prob=0.55)
        # edge = 1500 bps < 2000 threshold
        assert result.is_actionable is False

    def test_exactly_at_threshold(self):
        sig = ThresholdSignal(threshold_bps=1000.0)
        result = sig.evaluate(model_prob=0.70, market_prob=0.60)
        # edge = 1000 bps == threshold → actionable (>=)
        assert result.is_actionable is True

    def test_negative_edge_never_actionable(self):
        sig = ThresholdSignal(threshold_bps=0.0)
        result = sig.evaluate(model_prob=0.40, market_prob=0.55)
        assert result.is_actionable is False

    def test_has_rationale(self):
        sig = ThresholdSignal(threshold_bps=500.0)
        result = sig.evaluate(model_prob=0.70, market_prob=0.55)
        assert result.signal_type == "threshold"


# ---------------------------------------------------------------------------
# ConfidenceWeightedSignal
# ---------------------------------------------------------------------------


class TestConfidenceWeightedSignal:
    """Discounts the raw edge by model uncertainty.

    confidence_score = 1 - interval_width
    adjusted_edge = raw_edge_bps * confidence_score

    Wide intervals → low confidence → smaller adjusted edge.
    This prevents overconfident action on unreliable estimates.
    """

    def test_high_confidence_preserves_edge(self):
        """Tight interval (width=0.1) → confidence=0.9, small discount."""
        sig = ConfidenceWeightedSignal()
        result = sig.evaluate(
            model_prob=0.70,
            market_prob=0.55,
            interval_width=0.10,
        )
        # raw edge = 1500 bps, confidence = 0.90
        assert result.edge_bps == pytest.approx(1500.0)
        assert result.confidence_score == pytest.approx(0.90)
        assert result.adjusted_edge_bps == pytest.approx(1350.0)

    def test_low_confidence_reduces_edge(self):
        """Wide interval (width=0.6) → confidence=0.4, large discount."""
        sig = ConfidenceWeightedSignal()
        result = sig.evaluate(
            model_prob=0.70,
            market_prob=0.55,
            interval_width=0.60,
        )
        assert result.confidence_score == pytest.approx(0.40)
        assert result.adjusted_edge_bps == pytest.approx(600.0)

    def test_max_uncertainty_zeros_out(self):
        """Width=1.0 → confidence=0 → adjusted edge = 0."""
        sig = ConfidenceWeightedSignal()
        result = sig.evaluate(
            model_prob=0.70,
            market_prob=0.55,
            interval_width=1.0,
        )
        assert result.adjusted_edge_bps == pytest.approx(0.0)
        assert result.is_actionable is False

    def test_actionable_uses_adjusted_edge(self):
        """Actionable threshold is applied to adjusted edge, not raw."""
        sig = ConfidenceWeightedSignal(threshold_bps=1000.0)
        # raw = 1500 bps, confidence = 0.5 → adjusted = 750 < 1000
        result = sig.evaluate(
            model_prob=0.70,
            market_prob=0.55,
            interval_width=0.50,
        )
        assert result.is_actionable is False

    def test_has_rationale(self):
        sig = ConfidenceWeightedSignal()
        result = sig.evaluate(model_prob=0.70, market_prob=0.55, interval_width=0.2)
        assert result.signal_type == "confidence_weighted"


# ---------------------------------------------------------------------------
# rank_signals
# ---------------------------------------------------------------------------


class TestRankSignals:
    """Rank a list of signal results by adjusted_edge_bps descending.
    Only actionable signals are included."""

    def test_ranks_by_adjusted_edge(self):
        results = [
            SignalResult(
                signal_type="a",
                edge_bps=1000.0,
                adjusted_edge_bps=500.0,
                is_actionable=True,
                rationale="x",
            ),
            SignalResult(
                signal_type="b",
                edge_bps=2000.0,
                adjusted_edge_bps=1800.0,
                is_actionable=True,
                rationale="y",
            ),
            SignalResult(
                signal_type="c",
                edge_bps=1500.0,
                adjusted_edge_bps=1200.0,
                is_actionable=True,
                rationale="z",
            ),
        ]
        ranked = rank_signals(results)
        assert [r.signal_type for r in ranked] == ["b", "c", "a"]

    def test_filters_non_actionable(self):
        results = [
            SignalResult(
                signal_type="good",
                edge_bps=1000.0,
                adjusted_edge_bps=800.0,
                is_actionable=True,
                rationale="x",
            ),
            SignalResult(
                signal_type="bad",
                edge_bps=-500.0,
                adjusted_edge_bps=-500.0,
                is_actionable=False,
                rationale="y",
            ),
        ]
        ranked = rank_signals(results)
        assert len(ranked) == 1
        assert ranked[0].signal_type == "good"

    def test_empty_input(self):
        assert rank_signals([]) == []
