"""Unit tests for research context use cases.

These use cases support the analyst's workflow: creating notes,
managing watchlists, and viewing research data per market.
"""

from datetime import UTC, datetime
from uuid import uuid4

from preddesk.application.research_use_cases import (
    AddNote,
    AddToWatchlist,
    CreateWatchlist,
    GetMarketResearch,
)
from preddesk.domain.entities import (
    Market,
    MarketStatus,
    MarketType,
)
from preddesk.infrastructure.in_memory_repos import (
    InMemoryMarketRepository,
    InMemoryResearchNoteRepository,
    InMemoryWatchlistItemRepository,
    InMemoryWatchlistRepository,
)

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return NOW


def _make_market():
    market = Market(
        market_id=uuid4(),
        event_id=uuid4(),
        source_market_id="mkt-res",
        market_type=MarketType.BINARY,
        venue="polymarket",
        status=MarketStatus.ACTIVE,
    )
    repo = InMemoryMarketRepository()
    repo.save(market)
    return market, repo


class TestAddNote:
    def test_creates_and_persists_note(self):
        market, _market_repo = _make_market()
        note_repo = InMemoryResearchNoteRepository()

        uc = AddNote(note_repo=note_repo, clock=FakeClock())
        result = uc.execute(
            market_id=market.market_id,
            content="Looks overpriced vs base rates.",
            tags=["overpriced"],
        )

        assert result is not None
        assert result.content == "Looks overpriced vs base rates."
        assert result.market_id == market.market_id

        notes = note_repo.list_by_market(market.market_id)
        assert len(notes) == 1

    def test_note_with_hypothesis(self):
        market, _ = _make_market()
        note_repo = InMemoryResearchNoteRepository()

        uc = AddNote(note_repo=note_repo, clock=FakeClock())
        result = uc.execute(
            market_id=market.market_id,
            content="Testing hypothesis.",
            hypothesis="P(rain) > 60% based on NOAA data.",
        )
        assert result.hypothesis is not None


class TestCreateWatchlist:
    def test_creates_watchlist(self):
        wl_repo = InMemoryWatchlistRepository()
        uc = CreateWatchlist(watchlist_repo=wl_repo, clock=FakeClock())

        result = uc.execute(name="Weather Markets", description="All weather bets.")
        assert result.name == "Weather Markets"

        stored = wl_repo.list_all()
        assert len(stored) == 1


class TestAddToWatchlist:
    def test_adds_market_to_watchlist(self):
        market, _ = _make_market()
        wl_repo = InMemoryWatchlistRepository()
        item_repo = InMemoryWatchlistItemRepository()

        # Create watchlist first
        wl_uc = CreateWatchlist(watchlist_repo=wl_repo, clock=FakeClock())
        wl = wl_uc.execute(name="Test WL")

        uc = AddToWatchlist(item_repo=item_repo, clock=FakeClock())
        item = uc.execute(
            watchlist_id=wl.watchlist_id,
            market_id=market.market_id,
            note="Tracking this one.",
        )

        assert item.watchlist_id == wl.watchlist_id
        assert item.market_id == market.market_id

        items = item_repo.list_by_watchlist(wl.watchlist_id)
        assert len(items) == 1


class TestGetMarketResearch:
    def test_returns_notes_for_market(self):
        market, _market_repo = _make_market()
        note_repo = InMemoryResearchNoteRepository()
        item_repo = InMemoryWatchlistItemRepository()

        # Add a note
        add_note = AddNote(note_repo=note_repo, clock=FakeClock())
        add_note.execute(market_id=market.market_id, content="Note 1.")
        add_note.execute(market_id=market.market_id, content="Note 2.")

        uc = GetMarketResearch(note_repo=note_repo, item_repo=item_repo)
        result = uc.execute(market_id=market.market_id)

        assert len(result["notes"]) == 2
        assert len(result["watchlist_items"]) == 0
