"""End-to-end test: ingest → estimate → signal → paper order → position.

This test exercises the full pipeline using in-memory repos, verifying
that the system can go from raw market data to a filled paper order
with a tracked position. All five application use cases are wired together.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from preddesk.application.use_cases import (
    DetectSignal,
    GenerateEstimate,
    IngestMarkets,
    SimulateOrder,
)
from preddesk.domain.paper_broker import (
    BidAskExecution,
    FeeModel,
    PaperBroker,
    RiskPolicy,
    SlippageModel,
)
from preddesk.domain.probability_models import BaseRateModel
from preddesk.domain.signal_engine import ProbabilityGapSignal
from preddesk.domain.value_objects import OrderSide
from preddesk.infrastructure.in_memory_repos import (
    InMemoryEventRepository,
    InMemoryMarketRepository,
    InMemoryModelEstimateRepository,
    InMemoryPaperOrderRepository,
    InMemoryPositionRepository,
    InMemoryPriceSnapshotRepository,
    InMemorySignalRepository,
)

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return NOW


class FakeProvider:
    """Simulates an external market data provider returning one market."""

    def fetch_active_markets(self) -> list[dict]:
        return [
            {
                "source_event_id": "evt-e2e-1",
                "source_market_id": "mkt-e2e-1",
                "event_title": "Will it rain tomorrow?",
                "event_category": "weather",
                "market_type": "BINARY",
                "venue": "polymarket",
                "best_bid": 0.40,
                "best_ask": 0.45,
                "last_price": 0.42,
                "volume": 1000,
            }
        ]

    def fetch_market_detail(self, source_market_id: str) -> dict:
        return {}

    def fetch_price_snapshot(self, source_market_id: str) -> dict:
        return {}


class TestIngestToPaperTradeFlow:
    """Full pipeline: ingest → estimate → signal → order → position."""

    def test_full_pipeline(self):
        # --- Shared repos ---
        event_repo = InMemoryEventRepository()
        market_repo = InMemoryMarketRepository()
        snapshot_repo = InMemoryPriceSnapshotRepository()
        estimate_repo = InMemoryModelEstimateRepository()
        signal_repo = InMemorySignalRepository()
        order_repo = InMemoryPaperOrderRepository()
        position_repo = InMemoryPositionRepository()
        clock = FakeClock()

        # --- Step 1: Ingest markets ---
        ingest_uc = IngestMarkets(
            provider=FakeProvider(),
            event_repo=event_repo,
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            clock=clock,
        )
        ingest_result = ingest_uc.execute()
        assert ingest_result.markets_ingested == 1
        assert ingest_result.snapshots_saved == 1
        assert ingest_result.errors == 0

        # Get the market that was created
        markets = market_repo.list_active()
        assert len(markets) == 1
        market = markets[0]

        # --- Step 2: Generate estimate ---
        model = BaseRateModel(successes=7, total=10)  # 70% probability
        estimate_uc = GenerateEstimate(
            market_repo=market_repo,
            estimate_repo=estimate_repo,
            clock=clock,
        )
        estimate = estimate_uc.execute(market_id=market.market_id, model=model)
        assert estimate is not None
        assert estimate.estimated_probability == pytest.approx(0.70)

        # --- Step 3: Detect signal ---
        signal_uc = DetectSignal(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            estimate_repo=estimate_repo,
            signal_repo=signal_repo,
            signal_evaluator=ProbabilityGapSignal(),
            clock=clock,
        )
        signal_result = signal_uc.execute(market_id=market.market_id)
        assert signal_result is not None
        # Model says 70%, market mid is (0.40+0.45)/2 = 0.425 → large positive edge
        assert signal_result.edge_bps > 0
        assert signal_result.is_actionable is True

        # Signal should be persisted
        signals = signal_repo.list_by_market(market.market_id)
        assert len(signals) == 1

        # --- Step 4: Simulate order ---
        broker = PaperBroker(
            execution_model=BidAskExecution(),
            slippage_model=SlippageModel(slippage_bps=0.0),
            fee_model=FeeModel(fee_rate=0.0),
            risk_policy=RiskPolicy(max_position_size=100.0, max_portfolio_exposure=10000.0),
        )
        portfolio_id = uuid4()
        order_uc = SimulateOrder(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            order_repo=order_repo,
            position_repo=position_repo,
            broker=broker,
            clock=clock,
        )
        order_result = order_uc.execute(
            portfolio_id=portfolio_id,
            market_id=market.market_id,
            side=OrderSide.BUY,
            quantity=10.0,
            signal_id=signals[0].signal_id,
        )

        # --- Step 5: Verify final state ---
        assert order_result is not None
        assert order_result.order.status.value == "FILLED"
        assert order_result.fill is not None
        assert order_result.fill.fill_quantity == pytest.approx(10.0)

        # Position should exist
        assert order_result.position.net_quantity == pytest.approx(10.0)

        # Order persisted
        orders = order_repo.list_by_portfolio(portfolio_id)
        assert len(orders) == 1

        # Position persisted
        positions = position_repo.list_by_portfolio(portfolio_id)
        assert len(positions) == 1
