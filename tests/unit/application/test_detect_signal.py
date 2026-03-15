"""Unit tests for the DetectSignal use case.

This use case compares the latest model estimate against the current
market price and emits a Signal if the edge is actionable.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from preddesk.application.use_cases import DetectSignal
from preddesk.domain.entities import (
    Market,
    MarketStatus,
    MarketType,
    ModelEstimate,
    PriceSnapshot,
)
from preddesk.domain.signal_engine import EVSignal
from preddesk.infrastructure.in_memory_repos import (
    InMemoryMarketRepository,
    InMemoryModelEstimateRepository,
    InMemoryPriceSnapshotRepository,
    InMemorySignalRepository,
)

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return NOW


def _setup():
    """Create repos with a market, snapshot, and estimate."""
    market_id = uuid4()
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
        best_bid=0.53,
        best_ask=0.57,
    )
    estimate = ModelEstimate(
        estimate_id=uuid4(),
        market_id=market_id,
        model_name="base_rate",
        version="1.0",
        estimated_probability=0.70,
        generated_at=NOW,
    )

    market_repo = InMemoryMarketRepository()
    market_repo.save(market)
    snapshot_repo = InMemoryPriceSnapshotRepository()
    snapshot_repo.save(snapshot)
    estimate_repo = InMemoryModelEstimateRepository()
    estimate_repo.save(estimate)
    signal_repo = InMemorySignalRepository()

    return market, market_repo, snapshot_repo, estimate_repo, signal_repo


class TestDetectSignal:
    def test_detects_positive_edge_signal(self):
        market, market_repo, snapshot_repo, estimate_repo, signal_repo = _setup()

        use_case = DetectSignal(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            estimate_repo=estimate_repo,
            signal_repo=signal_repo,
            signal_evaluator=EVSignal(),
            clock=FakeClock(),
        )

        result = use_case.execute(market_id=market.market_id)

        assert result is not None
        assert result.is_actionable is True
        # model=0.70 vs mid=0.55 → EV = 0.70 - 0.55 = 0.15
        assert result.expected_value == pytest.approx(0.15)

        # Should be persisted
        signals = signal_repo.list_by_market(market.market_id)
        assert len(signals) == 1

    def test_returns_none_when_no_estimate(self):
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
        snapshot_repo = InMemoryPriceSnapshotRepository()
        snapshot_repo.save(
            PriceSnapshot(
                snapshot_id=uuid4(),
                market_id=market_id,
                captured_at=NOW,
                best_bid=0.50,
                best_ask=0.55,
            )
        )

        use_case = DetectSignal(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            estimate_repo=InMemoryModelEstimateRepository(),
            signal_repo=InMemorySignalRepository(),
            signal_evaluator=EVSignal(),
            clock=FakeClock(),
        )

        result = use_case.execute(market_id=market_id)
        assert result is None

    def test_returns_none_when_no_snapshot(self):
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

        use_case = DetectSignal(
            market_repo=market_repo,
            snapshot_repo=InMemoryPriceSnapshotRepository(),
            estimate_repo=InMemoryModelEstimateRepository(),
            signal_repo=InMemorySignalRepository(),
            signal_evaluator=EVSignal(),
            clock=FakeClock(),
        )

        result = use_case.execute(market_id=market_id)
        assert result is None
