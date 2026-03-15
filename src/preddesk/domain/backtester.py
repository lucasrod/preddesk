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
class BacktestMetrics:
    """Performance metrics for a completed backtest.

    Spec Section 14.2 metrics:
    - total_return: Sum of PnL across all closed trades.
    - hit_rate: Fraction of profitable round-trips (None if no trades).
    - max_drawdown: Maximum peak-to-trough decline in cumulative PnL.
    - avg_edge_captured: Mean PnL per round-trip (None if no round-trips).
    - avg_holding_time_seconds: Mean time between entry and exit fills (None if no round-trips).
    - turnover: Total quantity traded across all fills.
    """

    total_return: float
    hit_rate: float | None
    max_drawdown: float = 0.0
    avg_edge_captured: float | None = None
    avg_holding_time_seconds: float | None = None
    turnover: float = 0.0


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

        holding_times: list[float] = []  # seconds per round-trip

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

                if position_qty <= 0:
                    position_qty = 0.0
                    avg_cost = 0.0
                    entry_time = None

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

        metrics = BacktestMetrics(
            total_return=realized_pnl,
            hit_rate=hit_rate,
            max_drawdown=max_drawdown,
            avg_edge_captured=avg_edge,
            avg_holding_time_seconds=avg_ht,
            turnover=total_quantity_traded,
        )

        return BacktestResult(
            config=config,
            fills=fills,
            total_trades=len(fills),
            metrics=metrics,
        )
