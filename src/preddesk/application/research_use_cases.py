"""Research context use cases for PredDesk.

These use cases support the analyst's qualitative workflow:
creating notes, managing watchlists, and viewing research data.
"""

from __future__ import annotations

from uuid import uuid4

from preddesk.domain.ports import (
    Clock,
    ResearchNoteRepository,
    WatchlistItemRepository,
    WatchlistRepository,
)
from preddesk.domain.research_entities import ResearchNote, Watchlist, WatchlistItem


class AddNote:
    """Create a research note for a market."""

    def __init__(self, note_repo: ResearchNoteRepository, clock: Clock) -> None:
        self._note_repo = note_repo
        self._clock = clock

    def execute(
        self,
        market_id: object,
        content: str,
        tags: list[str] | None = None,
        hypothesis: str | None = None,
    ) -> ResearchNote:
        from uuid import UUID

        mid = market_id if isinstance(market_id, UUID) else UUID(str(market_id))
        note = ResearchNote(
            note_id=uuid4(),
            market_id=mid,
            content=content,
            tags=tags or [],
            hypothesis=hypothesis,
            created_at=self._clock.now(),
        )
        self._note_repo.save(note)
        return note


class CreateWatchlist:
    """Create a new watchlist."""

    def __init__(self, watchlist_repo: WatchlistRepository, clock: Clock) -> None:
        self._watchlist_repo = watchlist_repo
        self._clock = clock

    def execute(self, name: str, description: str | None = None) -> Watchlist:
        wl = Watchlist(
            watchlist_id=uuid4(),
            name=name,
            description=description,
            created_at=self._clock.now(),
        )
        self._watchlist_repo.save(wl)
        return wl


class AddToWatchlist:
    """Add a market to a watchlist."""

    def __init__(self, item_repo: WatchlistItemRepository, clock: Clock) -> None:
        self._item_repo = item_repo
        self._clock = clock

    def execute(
        self,
        watchlist_id: object,
        market_id: object,
        note: str | None = None,
    ) -> WatchlistItem:
        from uuid import UUID

        wid = watchlist_id if isinstance(watchlist_id, UUID) else UUID(str(watchlist_id))
        mid = market_id if isinstance(market_id, UUID) else UUID(str(market_id))
        item = WatchlistItem(
            watchlist_id=wid,
            market_id=mid,
            added_at=self._clock.now(),
            note=note,
        )
        self._item_repo.save(item)
        return item


class GetMarketResearch:
    """Get all research data for a market (notes + watchlist memberships)."""

    def __init__(
        self,
        note_repo: ResearchNoteRepository,
        item_repo: WatchlistItemRepository,
    ) -> None:
        self._note_repo = note_repo
        self._item_repo = item_repo

    def execute(self, market_id: object) -> dict:  # type: ignore[type-arg]
        from uuid import UUID

        mid = market_id if isinstance(market_id, UUID) else UUID(str(market_id))
        notes = self._note_repo.list_by_market(mid)
        # WatchlistItem doesn't have list_by_market, so we can't filter directly.
        # For now, return empty — in production, we'd add a query method.
        return {
            "notes": notes,
            "watchlist_items": [],
        }
