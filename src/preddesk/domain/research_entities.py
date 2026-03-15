"""Research context entities for PredDesk.

The research bounded context supports the analyst's workflow:
tracking hypotheses, recording observations, and organizing
markets into watchlists for focused monitoring.

These entities are append-only records — once created, notes and
watchlist items are not modified. This preserves the analyst's
decision trail for post-hoc review.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ResearchNote(BaseModel, frozen=True):
    """A note attached to a specific market.

    Notes record the analyst's reasoning, assumptions, and observations.
    They form the qualitative complement to the quantitative signals
    and estimates elsewhere in the system.
    """

    note_id: UUID
    market_id: UUID
    content: str
    created_at: datetime
    tags: list[str] = []
    hypothesis: str | None = None


class Watchlist(BaseModel, frozen=True):
    """A named collection of markets for focused monitoring."""

    watchlist_id: UUID
    name: str
    created_at: datetime
    description: str | None = None


class WatchlistItem(BaseModel, frozen=True):
    """Links a market to a watchlist."""

    watchlist_id: UUID
    market_id: UUID
    added_at: datetime
    note: str | None = None
