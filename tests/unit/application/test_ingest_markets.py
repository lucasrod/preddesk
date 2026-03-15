"""Unit tests for the IngestMarkets use case.

This use case fetches markets from an external provider, normalizes
them to canonical domain entities, and persists them. It demonstrates
the hexagonal architecture: the use case depends only on ports, and
tests inject in-memory fakes.
"""

from datetime import UTC, datetime

from preddesk.application.use_cases import IngestMarkets
from preddesk.infrastructure.in_memory_repos import (
    InMemoryEventRepository,
    InMemoryMarketRepository,
    InMemoryPriceSnapshotRepository,
    InMemoryRawPayloadRepository,
)


class FakeMarketDataProvider:
    """Fake external provider returning canned data."""

    def __init__(self, markets: list[dict]) -> None:  # type: ignore[type-arg]
        self._markets = markets

    def fetch_active_markets(self) -> list[dict]:  # type: ignore[type-arg]
        return self._markets

    def fetch_market_detail(self, source_market_id: str) -> dict:  # type: ignore[type-arg]
        for m in self._markets:
            if m["source_market_id"] == source_market_id:
                return m
        return {}

    def fetch_price_snapshot(self, source_market_id: str) -> dict:  # type: ignore[type-arg]
        return {"best_bid": 0.55, "best_ask": 0.60}


class FakeClock:
    def __init__(self, fixed_time: datetime) -> None:
        self._time = fixed_time

    def now(self) -> datetime:
        return self._time


NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


def _make_provider_data() -> list[dict]:  # type: ignore[type-arg]
    return [
        {
            "source_event_id": "evt-1",
            "event_title": "Will it rain tomorrow?",
            "event_category": "weather",
            "source_market_id": "mkt-1",
            "market_type": "BINARY",
            "venue": "polymarket",
            "best_bid": 0.55,
            "best_ask": 0.60,
        },
        {
            "source_event_id": "evt-2",
            "event_title": "Election 2028",
            "event_category": "politics",
            "source_market_id": "mkt-2",
            "market_type": "BINARY",
            "venue": "polymarket",
            "best_bid": 0.40,
            "best_ask": 0.45,
        },
    ]


class TestIngestMarkets:
    def test_ingests_new_markets(self):
        event_repo = InMemoryEventRepository()
        market_repo = InMemoryMarketRepository()
        snapshot_repo = InMemoryPriceSnapshotRepository()
        provider = FakeMarketDataProvider(_make_provider_data())
        clock = FakeClock(NOW)

        use_case = IngestMarkets(
            provider=provider,
            event_repo=event_repo,
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            clock=clock,
        )

        result = use_case.execute()

        assert result.markets_ingested == 2
        assert result.errors == 0
        assert len(market_repo.list_active()) == 2

    def test_skips_existing_markets(self):
        """If a market with the same source_market_id already exists,
        the use case should skip creation (upsert logic)."""
        event_repo = InMemoryEventRepository()
        market_repo = InMemoryMarketRepository()
        snapshot_repo = InMemoryPriceSnapshotRepository()
        provider = FakeMarketDataProvider(_make_provider_data())
        clock = FakeClock(NOW)

        use_case = IngestMarkets(
            provider=provider,
            event_repo=event_repo,
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            clock=clock,
        )

        # Ingest twice
        use_case.execute()
        result = use_case.execute()

        # Second run should still record snapshots but not duplicate markets
        assert len(market_repo.list_active()) == 2
        assert result.snapshots_saved == 2

    def test_saves_price_snapshots(self):
        event_repo = InMemoryEventRepository()
        market_repo = InMemoryMarketRepository()
        snapshot_repo = InMemoryPriceSnapshotRepository()
        provider = FakeMarketDataProvider(_make_provider_data())
        clock = FakeClock(NOW)

        use_case = IngestMarkets(
            provider=provider,
            event_repo=event_repo,
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            clock=clock,
        )

        use_case.execute()

        # Each market should have one snapshot
        for market in market_repo.list_active():
            latest = snapshot_repo.get_latest(market.market_id)
            assert latest is not None
            assert latest.best_bid is not None

    def test_handles_empty_provider(self):
        provider = FakeMarketDataProvider([])
        use_case = IngestMarkets(
            provider=provider,
            event_repo=InMemoryEventRepository(),
            market_repo=InMemoryMarketRepository(),
            snapshot_repo=InMemoryPriceSnapshotRepository(),
            clock=FakeClock(NOW),
        )
        result = use_case.execute()
        assert result.markets_ingested == 0

    def test_persists_raw_payloads(self):
        """When a raw_payload_repo is provided, each provider payload
        is stored as a RawMarketPayload for audit and replay."""
        event_repo = InMemoryEventRepository()
        market_repo = InMemoryMarketRepository()
        snapshot_repo = InMemoryPriceSnapshotRepository()
        raw_repo = InMemoryRawPayloadRepository()
        provider = FakeMarketDataProvider(_make_provider_data())
        clock = FakeClock(NOW)

        use_case = IngestMarkets(
            provider=provider,
            event_repo=event_repo,
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            clock=clock,
            raw_payload_repo=raw_repo,
        )

        result = use_case.execute()

        assert result.markets_ingested == 2
        all_payloads = raw_repo.list_by_provider("polymarket")
        assert len(all_payloads) == 2
        # Each payload should reference the canonical market
        for payload in all_payloads:
            assert payload.market_id is not None
            assert payload.raw_data is not None

    def test_works_without_raw_payload_repo(self):
        """Ingestion works fine without raw_payload_repo (backwards compatible)."""
        provider = FakeMarketDataProvider(_make_provider_data())
        use_case = IngestMarkets(
            provider=provider,
            event_repo=InMemoryEventRepository(),
            market_repo=InMemoryMarketRepository(),
            snapshot_repo=InMemoryPriceSnapshotRepository(),
            clock=FakeClock(NOW),
        )
        result = use_case.execute()
        assert result.markets_ingested == 2
