"""Signal engine for PredDesk.

Signals transform the difference between model probability and market
price into scored, explainable opportunities. All signal evaluators
are pure functions (or near-pure classes with no I/O).

Signal types:
- ProbabilityGapSignal: raw edge in basis points.
- EVSignal: expected value incorporating fees.
- ThresholdSignal: binary alert when edge exceeds a minimum.
- ConfidenceWeightedSignal: discounts edge by model uncertainty.

Every signal produces a SignalResult with a rationale string for
auditability — no signal should be a black box.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalResult:
    """The output of a signal evaluation.

    Attributes:
        signal_type: Identifier for the signal that produced this result.
        edge_bps: Raw edge in basis points (model - market) * 10_000.
        is_actionable: Whether this signal recommends action.
        rationale: Human-readable explanation of the signal.
        adjusted_edge_bps: Edge after confidence/fee adjustments.
        expected_value: EV of a hypothetical unit position (optional).
        confidence_score: Confidence in the estimate, in [0, 1] (optional).
    """

    signal_type: str
    edge_bps: float
    is_actionable: bool
    rationale: str
    adjusted_edge_bps: float = 0.0
    expected_value: float | None = None
    confidence_score: float | None = None


_FP_TOLERANCE = 0.01  # 0.01 bps — negligible for financial purposes


def _edge_bps(model_prob: float, market_prob: float) -> float:
    return (model_prob - market_prob) * 10_000.0


# ---------------------------------------------------------------------------
# ProbabilityGapSignal
# ---------------------------------------------------------------------------


class ProbabilityGapSignal:
    """Raw probability gap: model_prob - market_prob in basis points."""

    def evaluate(self, model_prob: float, market_prob: float, **kwargs: object) -> SignalResult:
        edge = _edge_bps(model_prob, market_prob)
        actionable = edge > 0.0
        return SignalResult(
            signal_type="probability_gap",
            edge_bps=edge,
            adjusted_edge_bps=edge,
            is_actionable=actionable,
            rationale=(f"Model={model_prob:.4f} vs Market={market_prob:.4f}, edge={edge:.0f} bps"),
        )


# ---------------------------------------------------------------------------
# EVSignal
# ---------------------------------------------------------------------------


class EVSignal:
    """Expected value signal for a unit-payout binary contract.

    EV = model_prob - (market_prob + fee_rate)

    Fees shift the break-even probability upward, making it harder
    for a signal to be actionable.
    """

    def __init__(self, fee_rate: float = 0.0) -> None:
        self._fee_rate = fee_rate

    def evaluate(self, model_prob: float, market_prob: float, **kwargs: object) -> SignalResult:
        effective_cost = market_prob + self._fee_rate
        ev = model_prob - effective_cost
        edge = _edge_bps(model_prob, market_prob)
        actionable = ev > 0.0
        return SignalResult(
            signal_type="expected_value",
            edge_bps=edge,
            adjusted_edge_bps=edge,
            expected_value=ev,
            is_actionable=actionable,
            rationale=(
                f"EV={ev:.4f} (model={model_prob:.4f}, cost={effective_cost:.4f}, "
                f"fee={self._fee_rate:.4f})"
            ),
        )


# ---------------------------------------------------------------------------
# ThresholdSignal
# ---------------------------------------------------------------------------


class ThresholdSignal:
    """Fires only when edge >= threshold_bps and edge > 0.

    Avoids noise from tiny mispricings that wouldn't survive
    transaction costs or estimation error.
    """

    def __init__(self, threshold_bps: float = 500.0) -> None:
        self._threshold_bps = threshold_bps

    def evaluate(self, model_prob: float, market_prob: float, **kwargs: object) -> SignalResult:
        edge = _edge_bps(model_prob, market_prob)
        # Tolerance for floating-point comparison (0.01 bps ≈ negligible)
        actionable = edge > 0.0 and edge >= self._threshold_bps - _FP_TOLERANCE
        return SignalResult(
            signal_type="threshold",
            edge_bps=edge,
            adjusted_edge_bps=edge,
            is_actionable=actionable,
            rationale=(f"Edge={edge:.0f} bps vs threshold={self._threshold_bps:.0f} bps"),
        )


# ---------------------------------------------------------------------------
# ConfidenceWeightedSignal
# ---------------------------------------------------------------------------


class ConfidenceWeightedSignal:
    """Discounts raw edge by model uncertainty.

    confidence_score = 1 - interval_width   (in [0, 1])
    adjusted_edge = raw_edge * confidence_score

    Wide confidence intervals → low confidence → smaller adjusted edge.
    The actionability threshold is applied to the adjusted edge.
    """

    def __init__(self, threshold_bps: float = 0.0) -> None:
        self._threshold_bps = threshold_bps

    def evaluate(
        self,
        model_prob: float,
        market_prob: float,
        **kwargs: object,
    ) -> SignalResult:
        raw_width = kwargs.get("interval_width", 0.0)
        interval_width = float(raw_width) if isinstance(raw_width, (int, float, str)) else 0.0
        edge = _edge_bps(model_prob, market_prob)
        confidence = max(0.0, 1.0 - interval_width)
        adjusted = edge * confidence
        actionable = adjusted > 0.0 and adjusted >= self._threshold_bps
        return SignalResult(
            signal_type="confidence_weighted",
            edge_bps=edge,
            adjusted_edge_bps=adjusted,
            confidence_score=confidence,
            is_actionable=actionable,
            rationale=(
                f"Raw edge={edge:.0f} bps, confidence={confidence:.2f}, "
                f"adjusted={adjusted:.0f} bps"
            ),
        )


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


def rank_signals(results: list[SignalResult]) -> list[SignalResult]:
    """Rank signal results by adjusted_edge_bps descending.

    Only actionable signals are included in the ranking.
    """
    actionable = [r for r in results if r.is_actionable]
    return sorted(actionable, key=lambda r: r.adjusted_edge_bps, reverse=True)
