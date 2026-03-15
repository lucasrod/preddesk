"""Unit tests for the ExecuteBacktest application use case.

This use case wraps the domain backtester with persistence:
it loads snapshots from a repository, runs the backtest, and
persists the resulting StrategyRun entity.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

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

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return NOW


class AlwaysBuyStrategy:
    """Buy 1 unit at every snapshot if no position."""

    def on_snapshot(
        self, snapshot: PriceSnapshot, position_qty: float
    ) -> tuple[OrderSide, float] | None:
        if position_qty == 0.0 and snapshot.mid_price is not None:
            return (OrderSide.BUY, 1.0)
        return None


def _make_broker() -> PaperBroker:
    return PaperBroker(
        execution_model=BidAskExecution(),
        slippage_model=SlippageModel(slippage_bps=0.0),
        fee_model=FeeModel(fee_rate=0.0),
        risk_policy=RiskPolicy(max_position_size=1000.0, max_portfolio_exposure=100000.0),
    )


def _setup():
    market_id = uuid4()
    market = Market(
        market_id=market_id,
        event_id=uuid4(),
        source_market_id="mkt-bt",
        market_type=MarketType.BINARY,
        venue="polymarket",
        status=MarketStatus.ACTIVE,
    )

    market_repo = InMemoryMarketRepository()
    market_repo.save(market)

    snapshot_repo = InMemoryPriceSnapshotRepository()
    for i in range(3):
        snap = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=market_id,
            captured_at=NOW + timedelta(hours=i),
            best_bid=0.50 + i * 0.05,
            best_ask=0.55 + i * 0.05,
        )
        snapshot_repo.save(snap)

    run_repo = InMemoryStrategyRunRepository()
    return market, market_repo, snapshot_repo, run_repo


class TestExecuteBacktest:
    def test_runs_backtest_and_persists_strategy_run(self):
        market, market_repo, snapshot_repo, run_repo = _setup()

        uc = ExecuteBacktest(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            strategy_run_repo=run_repo,
            broker=_make_broker(),
            clock=FakeClock(),
        )

        result = uc.execute(
            market_id=market.market_id,
            strategy=AlwaysBuyStrategy(),
            config=BacktestConfig(strategy_name="always_buy", version="1.0"),
        )

        assert result is not None
        assert result.total_trades > 0

        # StrategyRun should be persisted
        runs = run_repo.list_all()
        assert len(runs) == 1
        assert runs[0].strategy_name == "always_buy"
        assert runs[0].status == StrategyRunStatus.COMPLETED

    def test_returns_none_for_missing_market(self):
        _, market_repo, snapshot_repo, run_repo = _setup()

        uc = ExecuteBacktest(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            strategy_run_repo=run_repo,
            broker=_make_broker(),
            clock=FakeClock(),
        )

        result = uc.execute(
            market_id=uuid4(),  # nonexistent
            strategy=AlwaysBuyStrategy(),
            config=BacktestConfig(strategy_name="test", version="1.0"),
        )

        assert result is None

    def test_empty_snapshots_produces_zero_trades(self):
        market_id = uuid4()
        market = Market(
            market_id=market_id,
            event_id=uuid4(),
            source_market_id="empty",
            market_type=MarketType.BINARY,
            venue="polymarket",
            status=MarketStatus.ACTIVE,
        )
        market_repo = InMemoryMarketRepository()
        market_repo.save(market)
        snapshot_repo = InMemoryPriceSnapshotRepository()
        run_repo = InMemoryStrategyRunRepository()

        uc = ExecuteBacktest(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            strategy_run_repo=run_repo,
            broker=_make_broker(),
            clock=FakeClock(),
        )

        result = uc.execute(
            market_id=market_id,
            strategy=AlwaysBuyStrategy(),
            config=BacktestConfig(strategy_name="test", version="1.0"),
        )

        assert result is not None
        assert result.total_trades == 0
