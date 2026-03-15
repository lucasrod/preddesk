"""Unit tests for in-memory repository implementations.

These repos implement the domain ports using plain dicts/lists.
They are used for testing the application layer without any database.
"""

from datetime import UTC, datetime
from uuid import uuid4

from preddesk.domain.entities import (
    Event,
    EventStatus,
    Market,
    MarketStatus,
    MarketType,
    PriceSnapshot,
    RawMarketPayload,
)
from preddesk.infrastructure.in_memory_repos import (
    InMemoryEventRepository,
    InMemoryMarketRepository,
    InMemoryPriceSnapshotRepository,
    InMemoryRawPayloadRepository,
)

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class TestInMemoryEventRepository:
    def test_save_and_get(self):
        repo = InMemoryEventRepository()
        event = Event(
            event_id=uuid4(),
            source_event_id="poly-1",
            title="Test Event",
            category="test",
            status=EventStatus.OPEN,
            open_time=NOW,
        )
        repo.save(event)
        found = repo.get_by_id(event.event_id)
        assert found is not None
        assert found.title == "Test Event"

    def test_get_missing_returns_none(self):
        repo = InMemoryEventRepository()
        assert repo.get_by_id(uuid4()) is None

    def test_list_by_status(self):
        repo = InMemoryEventRepository()
        open_event = Event(
            event_id=uuid4(),
            source_event_id="a",
            title="Open",
            category="test",
            status=EventStatus.OPEN,
            open_time=NOW,
        )
        closed_event = Event(
            event_id=uuid4(),
            source_event_id="b",
            title="Closed",
            category="test",
            status=EventStatus.CLOSED,
            open_time=NOW,
        )
        repo.save(open_event)
        repo.save(closed_event)
        open_list = repo.list_by_status("OPEN")
        assert len(open_list) == 1
        assert open_list[0].title == "Open"


class TestInMemoryMarketRepository:
    def _make_market(self, source_id: str = "poly-mkt-1") -> Market:
        return Market(
            market_id=uuid4(),
            event_id=uuid4(),
            source_market_id=source_id,
            market_type=MarketType.BINARY,
            venue="polymarket",
            status=MarketStatus.ACTIVE,
        )

    def test_save_and_get(self):
        repo = InMemoryMarketRepository()
        market = self._make_market()
        repo.save(market)
        assert repo.get_by_id(market.market_id) is not None

    def test_find_by_source_id(self):
        repo = InMemoryMarketRepository()
        market = self._make_market("unique-source")
        repo.save(market)
        found = repo.find_by_source_id("unique-source")
        assert found is not None
        assert found.market_id == market.market_id

    def test_list_active(self):
        repo = InMemoryMarketRepository()
        active = self._make_market("a")
        repo.save(active)
        closed = Market(
            market_id=uuid4(),
            event_id=uuid4(),
            source_market_id="b",
            market_type=MarketType.BINARY,
            venue="polymarket",
            status=MarketStatus.CLOSED,
        )
        repo.save(closed)
        assert len(repo.list_active()) == 1


class TestInMemoryPriceSnapshotRepository:
    def test_save_and_get_latest(self):
        repo = InMemoryPriceSnapshotRepository()
        market_id = uuid4()
        old = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=market_id,
            captured_at=datetime(2025, 1, 1, tzinfo=UTC),
            best_bid=0.50,
            best_ask=0.55,
        )
        new = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=market_id,
            captured_at=datetime(2025, 6, 1, tzinfo=UTC),
            best_bid=0.55,
            best_ask=0.60,
        )
        repo.save(old)
        repo.save(new)
        latest = repo.get_latest(market_id)
        assert latest is not None
        assert latest.best_bid == 0.55

    def test_list_by_market(self):
        repo = InMemoryPriceSnapshotRepository()
        market_id = uuid4()
        for i in range(3):
            repo.save(
                PriceSnapshot(
                    snapshot_id=uuid4(),
                    market_id=market_id,
                    captured_at=datetime(2025, 1, i + 1, tzinfo=UTC),
                    best_bid=0.50 + i * 0.01,
                    best_ask=0.55 + i * 0.01,
                )
            )
        assert len(repo.list_by_market(market_id)) == 3

    def test_list_by_market_since(self):
        repo = InMemoryPriceSnapshotRepository()
        market_id = uuid4()
        for i in range(3):
            repo.save(
                PriceSnapshot(
                    snapshot_id=uuid4(),
                    market_id=market_id,
                    captured_at=datetime(2025, 1, i + 1, tzinfo=UTC),
                    best_bid=0.50,
                    best_ask=0.55,
                )
            )
        since = datetime(2025, 1, 2, tzinfo=UTC)
        result = repo.list_by_market(market_id, since=since)
        assert len(result) == 2  # Jan 2 and Jan 3


NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class TestInMemoryRawPayloadRepository:
    def test_save_and_list_by_provider(self):
        repo = InMemoryRawPayloadRepository()
        p1 = RawMarketPayload(
            payload_id=uuid4(),
            provider="polymarket",
            fetched_at=NOW,
            raw_data={"a": 1},
        )
        p2 = RawMarketPayload(
            payload_id=uuid4(),
            provider="metaculus",
            fetched_at=NOW,
            raw_data={"b": 2},
        )
        repo.save(p1)
        repo.save(p2)
        assert len(repo.list_by_provider("polymarket")) == 1
        assert len(repo.list_by_provider("metaculus")) == 1

    def test_list_by_market(self):
        repo = InMemoryRawPayloadRepository()
        mid = uuid4()
        repo.save(
            RawMarketPayload(
                payload_id=uuid4(),
                provider="polymarket",
                fetched_at=NOW,
                raw_data={"x": 1},
                market_id=mid,
            )
        )
        repo.save(
            RawMarketPayload(
                payload_id=uuid4(),
                provider="polymarket",
                fetched_at=NOW,
                raw_data={"y": 2},
            )
        )
        assert len(repo.list_by_market(mid)) == 1
