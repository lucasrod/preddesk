"""End-to-end test: backtest flow.

Exercises the full backtest pipeline: load snapshots → run strategy
through backtester → persist StrategyRun → verify metrics.

This uses the ExecuteBacktest application use case, which wraps the
domain Backtester with persistence.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from preddesk.application.use_cases import ExecuteBacktest
from preddesk.domain.backtester import BacktestConfig
from preddesk.domain.entities import (
    Market,
    MarketStatus,
    MarketType,
    PriceSnapshot,
    StrategyRunStatus,
)
from preddesk.domain.paper_broker import (
    BidAskExecution,
    FeeModel,
    PaperBroker,
    RiskPolicy,
    SlippageModel,
)
from preddesk.domain.value_objects import OrderSide
from preddesk.infrastructure.in_memory_repos import (
    InMemoryMarketRepository,
    InMemoryPriceSnapshotRepository,
    InMemoryStrategyRunRepository,
)

NOW = datetime(2025, 1, 1, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return NOW


class BuyThenSellStrategy:
    """Buys on first snapshot, sells on fourth — a simple round-trip."""

    def __init__(self):
        self._step = 0

    def on_snapshot(
        self, snapshot: PriceSnapshot, position_qty: float
    ) -> tuple[OrderSide, float] | None:
        self._step += 1
        if self._step == 1 and position_qty == 0.0:
            return (OrderSide.BUY, 5.0)
        if self._step == 4 and position_qty > 0.0:
            return (OrderSide.SELL, 5.0)
        return None


class TestBacktestFlow:
    def test_full_backtest_pipeline(self):
        """Ingest snapshots, run backtest, verify metrics and persistence."""
        market_id = uuid4()
        market = Market(
            market_id=market_id,
            event_id=uuid4(),
            source_market_id="mkt-bt-e2e",
            market_type=MarketType.BINARY,
            venue="polymarket",
            status=MarketStatus.ACTIVE,
        )

        market_repo = InMemoryMarketRepository()
        market_repo.save(market)

        snapshot_repo = InMemoryPriceSnapshotRepository()
        # Create 5 snapshots with rising prices
        prices = [
            (0.40, 0.45),  # step 1: buy at 0.45
            (0.45, 0.50),  # step 2: hold
            (0.50, 0.55),  # step 3: hold
            (0.55, 0.60),  # step 4: sell at 0.55
            (0.60, 0.65),  # step 5: done
        ]
        for i, (bid, ask) in enumerate(prices):
            snap = PriceSnapshot(
                snapshot_id=uuid4(),
                market_id=market_id,
                captured_at=NOW + timedelta(hours=i),
                best_bid=bid,
                best_ask=ask,
            )
            snapshot_repo.save(snap)

        strategy_run_repo = InMemoryStrategyRunRepository()

        broker = PaperBroker(
            execution_model=BidAskExecution(),
            slippage_model=SlippageModel(slippage_bps=0.0),
            fee_model=FeeModel(fee_rate=0.0),
            risk_policy=RiskPolicy(max_position_size=1000.0, max_portfolio_exposure=100000.0),
        )

        uc = ExecuteBacktest(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            strategy_run_repo=strategy_run_repo,
            broker=broker,
            clock=FakeClock(),
        )

        result = uc.execute(
            market_id=market_id,
            strategy=BuyThenSellStrategy(),
            config=BacktestConfig(strategy_name="buy_then_sell", version="1.0"),
        )

        # --- Verify backtest result ---
        assert result is not None
        assert result.total_trades == 2  # 1 buy + 1 sell

        # Buy 5 @ 0.45, sell 5 @ 0.55 → profit = 5 * 0.10 = 0.50
        assert result.metrics.total_return == pytest.approx(0.50)
        assert result.metrics.hit_rate == pytest.approx(1.0)
        assert result.metrics.max_drawdown == pytest.approx(0.0)  # no drawdown
        assert result.metrics.avg_edge_captured == pytest.approx(0.50)
        assert result.metrics.turnover == pytest.approx(10.0)  # 5 buy + 5 sell

        # Holding time: buy at hour 0, sell at hour 3 → 3 hours = 10800 seconds
        assert result.metrics.avg_holding_time_seconds == pytest.approx(10800.0)

        # --- Verify persistence ---
        runs = strategy_run_repo.list_all()
        assert len(runs) == 1
        run = runs[0]
        assert run.strategy_name == "buy_then_sell"
        assert run.status == StrategyRunStatus.COMPLETED
        assert run.summary_metrics is not None
        assert run.summary_metrics["total_return"] == pytest.approx(0.50)
