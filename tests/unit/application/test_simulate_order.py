"""Unit tests for the SimulateOrder use case.

This use case takes a signal (or manual intent), runs it through the
paper broker, and persists the resulting order, fill, and position update.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from preddesk.application.use_cases import SimulateOrder
from preddesk.domain.entities import (
    Market,
    MarketStatus,
    MarketType,
    PriceSnapshot,
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
    InMemoryPaperOrderRepository,
    InMemoryPositionRepository,
    InMemoryPriceSnapshotRepository,
)

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return NOW


def _make_broker() -> PaperBroker:
    return PaperBroker(
        execution_model=BidAskExecution(),
        slippage_model=SlippageModel(slippage_bps=50.0),
        fee_model=FeeModel(fee_rate=0.02),
        risk_policy=RiskPolicy(max_position_size=100.0, max_portfolio_exposure=10000.0),
    )


def _setup():
    market_id = uuid4()
    portfolio_id = uuid4()
    market = Market(
        market_id=market_id,
        event_id=uuid4(),
        source_market_id="mkt-1",
        market_type=MarketType.BINARY,
        venue="polymarket",
        status=MarketStatus.ACTIVE,
    )
    snapshot = PriceSnapshot(
        snapshot_id=uuid4(),
        market_id=market_id,
        captured_at=NOW,
        best_bid=0.55,
        best_ask=0.60,
    )

    market_repo = InMemoryMarketRepository()
    market_repo.save(market)
    snapshot_repo = InMemoryPriceSnapshotRepository()
    snapshot_repo.save(snapshot)
    order_repo = InMemoryPaperOrderRepository()
    position_repo = InMemoryPositionRepository()

    return market, portfolio_id, market_repo, snapshot_repo, order_repo, position_repo


class TestSimulateOrder:
    def test_buy_creates_order_and_position(self):
        market, portfolio_id, market_repo, snapshot_repo, order_repo, position_repo = _setup()

        use_case = SimulateOrder(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            order_repo=order_repo,
            position_repo=position_repo,
            broker=_make_broker(),
            clock=FakeClock(),
        )

        result = use_case.execute(
            portfolio_id=portfolio_id,
            market_id=market.market_id,
            side=OrderSide.BUY,
            quantity=10.0,
        )

        assert result is not None
        assert result.order.status.value == "FILLED"
        assert result.fill is not None
        assert result.fill.fill_quantity == pytest.approx(10.0)
        assert result.position.net_quantity == pytest.approx(10.0)

        # Should be persisted
        orders = order_repo.list_by_portfolio(portfolio_id)
        assert len(orders) == 1

    def test_rejected_order_when_exceeds_risk(self):
        market, portfolio_id, market_repo, snapshot_repo, order_repo, position_repo = _setup()

        use_case = SimulateOrder(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            order_repo=order_repo,
            position_repo=position_repo,
            broker=_make_broker(),
            clock=FakeClock(),
        )

        result = use_case.execute(
            portfolio_id=portfolio_id,
            market_id=market.market_id,
            side=OrderSide.BUY,
            quantity=200.0,  # exceeds max_position_size=100
        )

        assert result is not None
        assert result.order.status.value == "REJECTED"
        assert result.fill is None

    def test_returns_none_for_missing_snapshot(self):
        market_id = uuid4()
        market = Market(
            market_id=market_id,
            event_id=uuid4(),
            source_market_id="x",
            market_type=MarketType.BINARY,
            venue="polymarket",
            status=MarketStatus.ACTIVE,
        )
        market_repo = InMemoryMarketRepository()
        market_repo.save(market)

        use_case = SimulateOrder(
            market_repo=market_repo,
            snapshot_repo=InMemoryPriceSnapshotRepository(),
            order_repo=InMemoryPaperOrderRepository(),
            position_repo=InMemoryPositionRepository(),
            broker=_make_broker(),
            clock=FakeClock(),
        )

        result = use_case.execute(
            portfolio_id=uuid4(),
            market_id=market_id,
            side=OrderSide.BUY,
            quantity=10.0,
        )
        assert result is None
