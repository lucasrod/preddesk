"""Unit tests for the backtesting engine.

The backtester replays historical price snapshots in temporal order,
applies a strategy to generate signals and simulated trades, and
computes performance metrics.

Critical requirements:
- Deterministic: same inputs always produce the same output.
- No lookahead bias: at time t, only data from t and earlier is visible.
- Reproducible: configuration is serializable and tied to results.

See docs/domain/backtesting.md for methodology and pitfalls.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from preddesk.domain.backtester import (
    BacktestConfig,
    Backtester,
    BacktestResult,
)
from preddesk.domain.entities import PriceSnapshot
from preddesk.domain.paper_broker import (
    BidAskExecution,
    FeeModel,
    PaperBroker,
    RiskPolicy,
    SlippageModel,
)
from preddesk.domain.value_objects import OrderSide

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_TIME = datetime(2025, 1, 1, tzinfo=UTC)


def _make_snapshots(prices: list[tuple[float, float]], market_id=None):
    """Create a time series of price snapshots from (bid, ask) pairs."""
    mid = market_id or uuid4()
    return [
        PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=mid,
            captured_at=BASE_TIME + timedelta(hours=i),
            best_bid=bid,
            best_ask=ask,
        )
        for i, (bid, ask) in enumerate(prices)
    ]


class AlwaysBuyStrategy:
    """Trivial strategy: buy 1 unit at every snapshot if no position."""

    def on_snapshot(
        self, snapshot: PriceSnapshot, position_qty: float
    ) -> tuple[OrderSide, float] | None:
        if position_qty == 0.0 and snapshot.mid_price is not None:
            return (OrderSide.BUY, 1.0)
        return None


class NeverTradeStrategy:
    """Does nothing — useful for testing baseline metrics."""

    def on_snapshot(
        self, snapshot: PriceSnapshot, position_qty: float
    ) -> tuple[OrderSide, float] | None:
        return None


class BuyThenSellStrategy:
    """Buys on first snapshot, sells on third."""

    def __init__(self):
        self._step = 0

    def on_snapshot(
        self, snapshot: PriceSnapshot, position_qty: float
    ) -> tuple[OrderSide, float] | None:
        self._step += 1
        if self._step == 1 and position_qty == 0.0:
            return (OrderSide.BUY, 10.0)
        if self._step == 3 and position_qty > 0.0:
            return (OrderSide.SELL, 10.0)
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBacktestConfig:
    def test_creation(self):
        config = BacktestConfig(
            strategy_name="always_buy",
            version="1.0",
            params={"threshold": 500},
        )
        assert config.strategy_name == "always_buy"


class TestBacktester:
    def _default_broker(self) -> PaperBroker:
        return PaperBroker(
            execution_model=BidAskExecution(),
            slippage_model=SlippageModel(slippage_bps=0.0),
            fee_model=FeeModel(fee_rate=0.0),
            risk_policy=RiskPolicy(max_position_size=1000.0, max_portfolio_exposure=100000.0),
        )

    def test_basic_run(self):
        """Run a simple backtest with always-buy strategy."""
        snapshots = _make_snapshots([(0.50, 0.55), (0.55, 0.60), (0.60, 0.65)])
        bt = Backtester(broker=self._default_broker())

        result = bt.run(
            snapshots=snapshots,
            strategy=AlwaysBuyStrategy(),
            config=BacktestConfig(strategy_name="always_buy", version="1.0"),
        )

        assert result.total_trades > 0
        assert len(result.fills) > 0
        assert result.config.strategy_name == "always_buy"

    def test_no_trades_strategy(self):
        snapshots = _make_snapshots([(0.50, 0.55), (0.55, 0.60)])
        bt = Backtester(broker=self._default_broker())

        result = bt.run(
            snapshots=snapshots,
            strategy=NeverTradeStrategy(),
            config=BacktestConfig(strategy_name="never_trade", version="1.0"),
        )

        assert result.total_trades == 0
        assert len(result.fills) == 0

    def test_temporal_order(self):
        """Snapshots must be processed in chronological order.
        Even if provided out of order, the backtester sorts them."""
        market_id = uuid4()
        s1 = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=market_id,
            captured_at=BASE_TIME + timedelta(hours=2),
            best_bid=0.60,
            best_ask=0.65,
        )
        s2 = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=market_id,
            captured_at=BASE_TIME,
            best_bid=0.50,
            best_ask=0.55,
        )
        bt = Backtester(broker=self._default_broker())
        result = bt.run(
            snapshots=[s1, s2],  # out of order
            strategy=AlwaysBuyStrategy(),
            config=BacktestConfig(strategy_name="test", version="1.0"),
        )
        # The first fill should be at the earlier snapshot's ask price
        assert result.fills[0].fill_price == pytest.approx(0.55)

    def test_deterministic(self):
        """Same inputs → same output."""
        snapshots = _make_snapshots([(0.50, 0.55), (0.55, 0.60), (0.60, 0.65)])
        broker = self._default_broker()

        result1 = Backtester(broker=broker).run(
            snapshots=snapshots,
            strategy=AlwaysBuyStrategy(),
            config=BacktestConfig(strategy_name="test", version="1.0"),
        )
        result2 = Backtester(broker=broker).run(
            snapshots=snapshots,
            strategy=AlwaysBuyStrategy(),
            config=BacktestConfig(strategy_name="test", version="1.0"),
        )

        assert result1.total_trades == result2.total_trades
        assert len(result1.fills) == len(result2.fills)
        for f1, f2 in zip(result1.fills, result2.fills, strict=True):
            assert f1.fill_price == pytest.approx(f2.fill_price)

    def test_empty_snapshots(self):
        bt = Backtester(broker=self._default_broker())
        result = bt.run(
            snapshots=[],
            strategy=AlwaysBuyStrategy(),
            config=BacktestConfig(strategy_name="test", version="1.0"),
        )
        assert result.total_trades == 0


class TestBacktestMetrics:
    def _run_buy_then_sell(self) -> BacktestResult:
        """Buy at ask=0.55, sell at bid=0.65 → profit of 0.10 per unit."""
        snapshots = _make_snapshots(
            [
                (0.50, 0.55),  # step 1: buy at 0.55
                (0.55, 0.60),  # step 2: hold
                (0.65, 0.70),  # step 3: sell at 0.65
            ]
        )
        broker = PaperBroker(
            execution_model=BidAskExecution(),
            slippage_model=SlippageModel(slippage_bps=0.0),
            fee_model=FeeModel(fee_rate=0.0),
            risk_policy=RiskPolicy(max_position_size=1000.0, max_portfolio_exposure=100000.0),
        )
        bt = Backtester(broker=broker)
        return bt.run(
            snapshots=snapshots,
            strategy=BuyThenSellStrategy(),
            config=BacktestConfig(strategy_name="buy_sell", version="1.0"),
        )

    def test_total_return(self):
        result = self._run_buy_then_sell()
        # Buy 10 @ 0.55, sell 10 @ 0.65 → profit = 10 * 0.10 = 1.00
        assert result.metrics.total_return == pytest.approx(1.00)

    def test_trade_count(self):
        result = self._run_buy_then_sell()
        assert result.total_trades == 2  # 1 buy + 1 sell

    def test_hit_rate(self):
        """With one profitable round-trip, hit rate is 100%."""
        result = self._run_buy_then_sell()
        assert result.metrics.hit_rate == pytest.approx(1.0)

    def test_no_trades_metrics(self):
        bt = Backtester(
            broker=PaperBroker(
                execution_model=BidAskExecution(),
                slippage_model=SlippageModel(slippage_bps=0.0),
                fee_model=FeeModel(fee_rate=0.0),
                risk_policy=RiskPolicy(max_position_size=100.0, max_portfolio_exposure=10000.0),
            )
        )
        result = bt.run(
            snapshots=_make_snapshots([(0.50, 0.55)]),
            strategy=NeverTradeStrategy(),
            config=BacktestConfig(strategy_name="none", version="1.0"),
        )
        assert result.metrics.total_return == pytest.approx(0.0)
        assert result.metrics.hit_rate is None  # undefined with no trades

    def test_max_drawdown_profitable(self):
        """A single profitable round-trip has zero drawdown."""
        result = self._run_buy_then_sell()
        # Only one round-trip with profit, equity never dips below start
        assert result.metrics.max_drawdown == pytest.approx(0.0)

    def test_max_drawdown_with_loss(self):
        """Buy high, sell low produces a drawdown equal to the loss.

        Max drawdown measures the largest peak-to-trough decline in the
        cumulative PnL curve. For a single losing trade, it equals the loss.
        """
        snapshots = _make_snapshots(
            [
                (0.60, 0.65),  # step 1: buy at 0.65
                (0.55, 0.60),  # step 2: hold (price drops)
                (0.45, 0.50),  # step 3: sell at 0.45
            ]
        )
        broker = PaperBroker(
            execution_model=BidAskExecution(),
            slippage_model=SlippageModel(slippage_bps=0.0),
            fee_model=FeeModel(fee_rate=0.0),
            risk_policy=RiskPolicy(max_position_size=1000.0, max_portfolio_exposure=100000.0),
        )
        bt = Backtester(broker=broker)
        result = bt.run(
            snapshots=snapshots,
            strategy=BuyThenSellStrategy(),
            config=BacktestConfig(strategy_name="loss", version="1.0"),
        )
        # Buy 10 @ 0.65, sell 10 @ 0.45 → loss = 10 * 0.20 = 2.00
        assert result.metrics.total_return == pytest.approx(-2.00)
        assert result.metrics.max_drawdown == pytest.approx(2.00)

    def test_average_edge_captured(self):
        """Average edge captured = mean PnL per round-trip.

        For a single round-trip with profit 1.00, avg edge = 1.00.
        """
        result = self._run_buy_then_sell()
        assert result.metrics.avg_edge_captured == pytest.approx(1.00)

    def test_avg_holding_time(self):
        """Average time between buy and sell fills.

        BuyThenSellStrategy buys at step 1 (hour 0), sells at step 3
        (hour 2), so holding time is 2 hours = 7200 seconds.
        """
        result = self._run_buy_then_sell()
        assert result.metrics.avg_holding_time_seconds == pytest.approx(7200.0)

    def test_turnover(self):
        """Turnover = total quantity traded across all fills.

        Buy 10 + sell 10 = 20 total units traded.
        """
        result = self._run_buy_then_sell()
        assert result.metrics.turnover == pytest.approx(20.0)

    def test_no_trades_extended_metrics(self):
        """With no trades, extended metrics should have sensible defaults."""
        bt = Backtester(
            broker=PaperBroker(
                execution_model=BidAskExecution(),
                slippage_model=SlippageModel(slippage_bps=0.0),
                fee_model=FeeModel(fee_rate=0.0),
                risk_policy=RiskPolicy(max_position_size=100.0, max_portfolio_exposure=10000.0),
            )
        )
        result = bt.run(
            snapshots=_make_snapshots([(0.50, 0.55)]),
            strategy=NeverTradeStrategy(),
            config=BacktestConfig(strategy_name="none", version="1.0"),
        )
        assert result.metrics.avg_edge_captured is None
        assert result.metrics.avg_holding_time_seconds is None
        assert result.metrics.turnover == pytest.approx(0.0)

    def test_sharpe_ratio_single_profitable_trade(self):
        """Sharpe ratio = mean(returns) / std(returns).
        With a single round-trip, std is 0, so Sharpe is None."""
        result = self._run_buy_then_sell()
        assert result.metrics.sharpe_ratio is None  # undefined for single trade

    def test_sharpe_ratio_multiple_trades(self):
        """With multiple round-trips of varying PnL, Sharpe is well-defined.

        Sharpe = mean(round_trip_pnls) / std(round_trip_pnls)
        """

        class TwoRoundTrips:
            """Buys and sells twice."""

            def __init__(self):
                self._step = 0

            def on_snapshot(self, snapshot, position_qty):
                self._step += 1
                if self._step == 1 and position_qty == 0.0:
                    return (OrderSide.BUY, 10.0)
                if self._step == 2 and position_qty > 0.0:
                    return (OrderSide.SELL, 10.0)
                if self._step == 3 and position_qty == 0.0:
                    return (OrderSide.BUY, 10.0)
                if self._step == 4 and position_qty > 0.0:
                    return (OrderSide.SELL, 10.0)
                return None

        snapshots = _make_snapshots([
            (0.50, 0.55),  # buy at 0.55
            (0.65, 0.70),  # sell at 0.65 → profit 1.00
            (0.40, 0.45),  # buy at 0.45
            (0.55, 0.60),  # sell at 0.55 → profit 1.00
        ])
        broker = PaperBroker(
            execution_model=BidAskExecution(),
            slippage_model=SlippageModel(slippage_bps=0.0),
            fee_model=FeeModel(fee_rate=0.0),
            risk_policy=RiskPolicy(max_position_size=1000.0, max_portfolio_exposure=100000.0),
        )
        bt = Backtester(broker=broker)
        result = bt.run(
            snapshots=snapshots,
            strategy=TwoRoundTrips(),
            config=BacktestConfig(strategy_name="two_rt", version="1.0"),
        )
        # Both round-trips profit 1.00 each — returns are nearly identical
        # Sharpe is very large (near-zero std) or defined; key point is it's positive
        assert result.metrics.sharpe_ratio is not None
        assert result.metrics.sharpe_ratio > 0

    def test_sharpe_ratio_with_variance(self):
        """Sharpe with different returns: profit 1.00 and loss -2.00.

        mean = (1.00 + (-2.00)) / 2 = -0.50
        std = sqrt(((1.00 - (-0.50))^2 + (-2.00 - (-0.50))^2) / 1) = sqrt((2.25+2.25)/1) ≈ 2.121
        Sharpe ≈ -0.50 / 2.121 ≈ -0.2357
        """

        class WinLoseStrategy:
            def __init__(self):
                self._step = 0

            def on_snapshot(self, snapshot, position_qty):
                self._step += 1
                if self._step == 1 and position_qty == 0.0:
                    return (OrderSide.BUY, 10.0)
                if self._step == 2 and position_qty > 0.0:
                    return (OrderSide.SELL, 10.0)
                if self._step == 3 and position_qty == 0.0:
                    return (OrderSide.BUY, 10.0)
                if self._step == 4 and position_qty > 0.0:
                    return (OrderSide.SELL, 10.0)
                return None

        snapshots = _make_snapshots([
            (0.50, 0.55),  # buy at 0.55
            (0.65, 0.70),  # sell at 0.65 → profit 1.00
            (0.60, 0.65),  # buy at 0.65
            (0.45, 0.50),  # sell at 0.45 → loss -2.00
        ])
        broker = PaperBroker(
            execution_model=BidAskExecution(),
            slippage_model=SlippageModel(slippage_bps=0.0),
            fee_model=FeeModel(fee_rate=0.0),
            risk_policy=RiskPolicy(max_position_size=1000.0, max_portfolio_exposure=100000.0),
        )
        bt = Backtester(broker=broker)
        result = bt.run(
            snapshots=snapshots,
            strategy=WinLoseStrategy(),
            config=BacktestConfig(strategy_name="win_lose", version="1.0"),
        )
        assert result.metrics.sharpe_ratio is not None
        assert result.metrics.sharpe_ratio < 0  # negative edge

    def test_no_trades_sharpe_is_none(self):
        bt = Backtester(
            broker=PaperBroker(
                execution_model=BidAskExecution(),
                slippage_model=SlippageModel(slippage_bps=0.0),
                fee_model=FeeModel(fee_rate=0.0),
                risk_policy=RiskPolicy(max_position_size=100.0, max_portfolio_exposure=10000.0),
            )
        )
        result = bt.run(
            snapshots=_make_snapshots([(0.50, 0.55)]),
            strategy=NeverTradeStrategy(),
            config=BacktestConfig(strategy_name="none", version="1.0"),
        )
        assert result.metrics.sharpe_ratio is None

    def test_brier_score_profitable_trade(self):
        """Brier score measures calibration of the implied buy signal.

        When the backtester buys at mid_price (the market's implied prob)
        and the trade is profitable, the outcome is 1 (success).

        Brier = mean((forecast - outcome)^2)

        Buy at mid=0.525, trade is profitable → outcome=1
        Brier = (0.525 - 1)^2 = 0.225625
        """
        result = self._run_buy_then_sell()
        assert result.metrics.brier_score is not None
        # mid_price at buy time: (0.50+0.55)/2 = 0.525
        expected_brier = (0.525 - 1.0) ** 2
        assert result.metrics.brier_score == pytest.approx(expected_brier, rel=1e-3)

    def test_no_round_trips_brier_is_none(self):
        bt = Backtester(
            broker=PaperBroker(
                execution_model=BidAskExecution(),
                slippage_model=SlippageModel(slippage_bps=0.0),
                fee_model=FeeModel(fee_rate=0.0),
                risk_policy=RiskPolicy(max_position_size=100.0, max_portfolio_exposure=10000.0),
            )
        )
        result = bt.run(
            snapshots=_make_snapshots([(0.50, 0.55)]),
            strategy=NeverTradeStrategy(),
            config=BacktestConfig(strategy_name="none", version="1.0"),
        )
        assert result.metrics.brier_score is None

    def test_calibration_buckets(self):
        """Calibration buckets group forecasts by predicted probability range
        and compare to observed outcome frequency.

        Each bucket: (bucket_lower, bucket_upper, avg_forecast, observed_freq, count).
        """
        result = self._run_buy_then_sell()
        buckets = result.metrics.calibration_buckets
        assert buckets is not None
        assert len(buckets) > 0
        # Each bucket is a dict with expected keys
        bucket = buckets[0]
        assert "lower" in bucket
        assert "upper" in bucket
        assert "avg_forecast" in bucket
        assert "observed_freq" in bucket
        assert "count" in bucket
