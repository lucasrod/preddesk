"""Unit tests for the GenerateEstimate use case.

This use case takes a market, runs a probability model, and persists
the resulting ModelEstimate. It demonstrates the separation between
domain models (probability_models.py) and application orchestration.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from preddesk.application.use_cases import GenerateEstimate
from preddesk.domain.entities import (
    Market,
    MarketStatus,
    MarketType,
)
from preddesk.domain.probability_models import BaseRateModel
from preddesk.infrastructure.in_memory_repos import (
    InMemoryMarketRepository,
    InMemoryModelEstimateRepository,
)

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return NOW


def _make_market() -> Market:
    return Market(
        market_id=uuid4(),
        event_id=uuid4(),
        source_market_id="mkt-1",
        market_type=MarketType.BINARY,
        venue="polymarket",
        status=MarketStatus.ACTIVE,
    )


class TestGenerateEstimate:
    def test_generates_and_persists_estimate(self):
        market = _make_market()
        market_repo = InMemoryMarketRepository()
        market_repo.save(market)

        estimate_repo = InMemoryModelEstimateRepository()
        model = BaseRateModel(successes=7, total=10)

        use_case = GenerateEstimate(
            market_repo=market_repo,
            estimate_repo=estimate_repo,
            clock=FakeClock(),
        )

        result = use_case.execute(market_id=market.market_id, model=model)

        assert result is not None
        assert result.estimated_probability == pytest.approx(0.70)
        assert result.model_name == "base_rate"

        # Should be persisted
        latest = estimate_repo.get_latest(market.market_id)
        assert latest is not None
        assert latest.estimate_id == result.estimate_id

    def test_includes_confidence_interval(self):
        market = _make_market()
        market_repo = InMemoryMarketRepository()
        market_repo.save(market)
        estimate_repo = InMemoryModelEstimateRepository()
        model = BaseRateModel(successes=7, total=10)

        use_case = GenerateEstimate(
            market_repo=market_repo,
            estimate_repo=estimate_repo,
            clock=FakeClock(),
        )

        result = use_case.execute(market_id=market.market_id, model=model)
        assert result is not None
        assert result.lower_bound is not None
        assert result.upper_bound is not None
        assert result.lower_bound < result.estimated_probability < result.upper_bound

    def test_returns_none_for_missing_market(self):
        use_case = GenerateEstimate(
            market_repo=InMemoryMarketRepository(),
            estimate_repo=InMemoryModelEstimateRepository(),
            clock=FakeClock(),
        )
        result = use_case.execute(market_id=uuid4(), model=BaseRateModel(successes=5, total=10))
        assert result is None
