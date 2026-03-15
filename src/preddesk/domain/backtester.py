"""Backtesting engine for PredDesk.

Replays historical price snapshots in temporal order, executes a
strategy, and computes performance metrics. The engine enforces:

1. **Temporal ordering** — snapshots are sorted chronologically.
2. **No lookahead bias** — at time t, only data from t and earlier
   is visible to the strategy.
3. **Determinism** — same inputs always produce the same output.

See docs/domain/backtesting.md for methodology and pitfalls.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from preddesk.domain.entities import PriceSnapshot
from preddesk.domain.paper_broker import FillResult, PaperBroker
from preddesk.domain.value_objects import OrderSide

# ---------------------------------------------------------------------------
# Strategy protocol
# ---------------------------------------------------------------------------


class Strategy(Protocol):
    """A strategy decides whether to trade given a snapshot and current position.

    Returns (side, quantity) if a trade should be placed, or None to skip.
    """

    def on_snapshot(
        self, snapshot: PriceSnapshot, position_qty: float
    ) -> tuple[OrderSide, float] | None: ...


# ---------------------------------------------------------------------------
# Config & results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestConfig:
    """Serializable configuration for a backtest run."""

    strategy_name: str
    version: str
    params: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CalibrationBucket:
    """A single bucket in a calibration analysis."""

    lower: float
    upper: float
    avg_forecast: float
    observed_freq: float
    count: int


@dataclass(frozen=True)
class BacktestMetrics:
    """Performance metrics for a completed backtest.

    Spec Section 14.2 metrics:
    - total_return: Sum of PnL across all closed trades.
    - hit_rate: Fraction of profitable round-trips (None if no trades).
    - max_drawdown: Maximum peak-to-trough decline in cumulative PnL.
    - avg_edge_captured: Mean PnL per round-trip (None if no round-trips).
    - avg_holding_time_seconds: Mean time between entry and exit fills.
    - turnover: Total quantity traded across all fills.
    - sharpe_ratio: mean(round_trip_pnl) / std(round_trip_pnl). None if <2 distinct values.
    - brier_score: mean((forecast - outcome)^2) where forecast is the mid_price
      at entry and outcome is 1 if profitable, 0 otherwise. None if no round-trips.
    - calibration_buckets: list of CalibrationBucket dicts grouping forecasts by
      predicted probability and comparing to observed frequency.
    """

    total_return: float
    hit_rate: float | None
    max_drawdown: float = 0.0
    avg_edge_captured: float | None = None
    avg_holding_time_seconds: float | None = None
    turnover: float = 0.0
    sharpe_ratio: float | None = None
    brier_score: float | None = None
    calibration_buckets: list[dict[str, object]] | None = None


@dataclass
class BacktestResult:
    """Full result of a backtest run."""

    config: BacktestConfig
    fills: list[FillResult]
    total_trades: int
    metrics: BacktestMetrics


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------


def _compute_calibration_buckets(
    pairs: list[tuple[float, int]],
    n_buckets: int = 10,
) -> list[dict[str, object]]:
    """Group forecast/outcome pairs into calibration buckets.

    Each bucket spans a range of predicted probabilities [lower, upper)
    and reports the average forecast, observed frequency (fraction of
    outcomes = 1), and count.
    """
    width = 1.0 / n_buckets
    buckets: list[dict[str, object]] = []
    for i in range(n_buckets):
        lo = i * width
        hi = (i + 1) * width
        in_bucket = [(f, o) for f, o in pairs if lo <= f < hi or (i == n_buckets - 1 and f == hi)]
        if not in_bucket:
            continue
        avg_f = sum(f for f, _ in in_bucket) / len(in_bucket)
        obs_freq = sum(o for _, o in in_bucket) / len(in_bucket)
        buckets.append({
            "lower": lo,
            "upper": hi,
            "avg_forecast": avg_f,
            "observed_freq": obs_freq,
            "count": len(in_bucket),
        })
    return buckets


class Backtester:
    """Replays snapshots through a strategy and paper broker.

    The backtester maintains a simple position tracker (quantity and
    average cost) to feed back into the strategy and compute PnL.
    """

    def __init__(self, broker: PaperBroker) -> None:
        self._broker = broker

    def run(
        self,
        snapshots: list[PriceSnapshot],
        strategy: Strategy,
        config: BacktestConfig,
    ) -> BacktestResult:
        # Sort chronologically — prevents lookahead bias
        sorted_snaps = sorted(snapshots, key=lambda s: s.captured_at)

        fills: list[FillResult] = []
        fill_timestamps: list[datetime] = []
        fill_sides: list[OrderSide] = []
        position_qty = 0.0
        avg_cost = 0.0
        realized_pnl = 0.0
        round_trips: list[float] = []  # PnL per closed trade
        peak_pnl = 0.0
        max_drawdown = 0.0
        total_quantity_traded = 0.0

        # Track entry times for holding-time calculation
        entry_time: datetime | None = None
        entry_mid_price: float | None = None  # for Brier score / calibration

        holding_times: list[float] = []  # seconds per round-trip
        forecast_outcome_pairs: list[tuple[float, int]] = []  # (mid_price, 1 if profitable else 0)

        for snap in sorted_snaps:
            if snap.best_bid is None or snap.best_ask is None:
                continue

            action = strategy.on_snapshot(snap, position_qty)
            if action is None:
                continue

            side, quantity = action

            fill = self._broker.execute(
                side=side,
                quantity=quantity,
                best_bid=snap.best_bid,
                best_ask=snap.best_ask,
                current_exposure=position_qty,
            )

            if fill is None:
                continue

            fills.append(fill)
            fill_timestamps.append(snap.captured_at)
            fill_sides.append(side)
            total_quantity_traded += fill.fill_quantity

            if side == OrderSide.BUY:
                if position_qty == 0.0:
                    entry_time = snap.captured_at
                    entry_mid_price = snap.mid_price
                # Update position
                total_cost = avg_cost * position_qty + fill.fill_price * fill.fill_quantity
                position_qty += fill.fill_quantity
                avg_cost = total_cost / position_qty if position_qty > 0 else 0.0
            elif side == OrderSide.SELL:
                # Realize PnL
                pnl = (fill.fill_price - avg_cost) * fill.fill_quantity
                pnl -= float(fill.fee_amount)
                realized_pnl += pnl
                round_trips.append(pnl)
                position_qty -= fill.fill_quantity

                # Track holding time
                if entry_time is not None:
                    dt = (snap.captured_at - entry_time).total_seconds()
                    holding_times.append(dt)

                # Track forecast/outcome for Brier score and calibration
                if entry_mid_price is not None:
                    outcome = 1 if pnl > 0 else 0
                    forecast_outcome_pairs.append((entry_mid_price, outcome))

                if position_qty <= 0:
                    position_qty = 0.0
                    avg_cost = 0.0
                    entry_time = None
                    entry_mid_price = None

            # Track equity curve for max drawdown
            peak_pnl = max(peak_pnl, realized_pnl)
            drawdown = peak_pnl - realized_pnl
            max_drawdown = max(max_drawdown, drawdown)

        # Compute metrics
        if round_trips:
            profitable = sum(1 for pnl in round_trips if pnl > 0)
            hit_rate: float | None = profitable / len(round_trips)
            avg_edge: float | None = sum(round_trips) / len(round_trips)
        else:
            hit_rate = None
            avg_edge = None

        avg_ht: float | None = sum(holding_times) / len(holding_times) if holding_times else None

        # Sharpe ratio: mean / std of round-trip PnLs (None if <2 distinct values)
        sharpe: float | None = None
        if len(round_trips) >= 2:
            mean_pnl = sum(round_trips) / len(round_trips)
            variance = sum((r - mean_pnl) ** 2 for r in round_trips) / (len(round_trips) - 1)
            std_pnl = math.sqrt(variance)
            if std_pnl > 0:
                sharpe = mean_pnl / std_pnl

        # Brier score and calibration from forecast/outcome pairs
        brier: float | None = None
        cal_buckets: list[dict[str, object]] | None = None
        if forecast_outcome_pairs:
            brier = sum(
                (f - o) ** 2 for f, o in forecast_outcome_pairs
            ) / len(forecast_outcome_pairs)
            cal_buckets = _compute_calibration_buckets(forecast_outcome_pairs)

        metrics = BacktestMetrics(
            total_return=realized_pnl,
            hit_rate=hit_rate,
            max_drawdown=max_drawdown,
            avg_edge_captured=avg_edge,
            avg_holding_time_seconds=avg_ht,
            turnover=total_quantity_traded,
            sharpe_ratio=sharpe,
            brier_score=brier,
            calibration_buckets=cal_buckets,
        )

        return BacktestResult(
            config=config,
            fills=fills,
            total_trades=len(fills),
            metrics=metrics,
        )
