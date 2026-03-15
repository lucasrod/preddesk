"""Unit tests for research context entities.

The research context (Bounded Context F) supports the analytical
workflow: tracking hypotheses, associating notes with markets,
and maintaining watchlists for focused monitoring.
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from preddesk.domain.research_entities import ResearchNote, Watchlist, WatchlistItem

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


class TestResearchNote:
    """Notes allow the user to record reasoning, assumptions, and
    observations about specific markets. They are append-only records
    of the analyst's thought process."""

    def test_creation(self):
        note = ResearchNote(
            note_id=uuid4(),
            market_id=uuid4(),
            content="Market seems overpriced relative to base rates.",
            tags=["overpriced", "weather"],
            created_at=NOW,
        )
        assert note.content == "Market seems overpriced relative to base rates."
        assert "overpriced" in note.tags

    def test_optional_hypothesis(self):
        note = ResearchNote(
            note_id=uuid4(),
            market_id=uuid4(),
            content="Testing hypothesis link.",
            hypothesis="Rain probability > 60% based on historical data.",
            created_at=NOW,
        )
        assert note.hypothesis is not None

    def test_defaults(self):
        note = ResearchNote(
            note_id=uuid4(),
            market_id=uuid4(),
            content="Minimal note.",
            created_at=NOW,
        )
        assert note.tags == []
        assert note.hypothesis is None

    def test_immutable(self):
        note = ResearchNote(
            note_id=uuid4(),
            market_id=uuid4(),
            content="Cannot change.",
            created_at=NOW,
        )
        with pytest.raises(ValidationError):
            note.content = "New content"


class TestWatchlist:
    """Watchlists let users group markets for focused monitoring."""

    def test_creation(self):
        wl = Watchlist(
            watchlist_id=uuid4(),
            name="Weather Markets",
            description="All weather-related prediction markets.",
            created_at=NOW,
        )
        assert wl.name == "Weather Markets"

    def test_optional_description(self):
        wl = Watchlist(
            watchlist_id=uuid4(),
            name="Quick List",
            created_at=NOW,
        )
        assert wl.description is None


class TestWatchlistItem:
    """Links a market to a watchlist with optional notes."""

    def test_creation(self):
        item = WatchlistItem(
            watchlist_id=uuid4(),
            market_id=uuid4(),
            added_at=NOW,
            note="Tracking for edge opportunity.",
        )
        assert item.note == "Tracking for edge opportunity."

    def test_optional_note(self):
        item = WatchlistItem(
            watchlist_id=uuid4(),
            market_id=uuid4(),
            added_at=NOW,
        )
        assert item.note is None
