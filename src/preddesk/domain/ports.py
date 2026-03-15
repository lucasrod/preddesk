"""Domain ports (interfaces) for PredDesk.

Ports define the contracts between the domain/application layers and
infrastructure. They are Protocol classes — infrastructure adapters
implement them, and application services depend on them.

This is the core of hexagonal architecture: the domain never imports
infrastructure; it only defines what it needs through these protocols.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from preddesk.domain.entities import (
    Event,
    Market,
    ModelEstimate,
    PaperFill,
    PaperOrder,
    Portfolio,
    Position,
    PriceSnapshot,
    RawMarketPayload,
    Signal,
    StrategyRun,
)
from preddesk.domain.research_entities import ResearchNote, Watchlist, WatchlistItem

# ---------------------------------------------------------------------------
# Clock — testable time
# ---------------------------------------------------------------------------


class Clock(Protocol):
    """Abstraction for current time, enabling deterministic tests."""

    def now(self) -> datetime: ...


# ---------------------------------------------------------------------------
# Unit of Work
# ---------------------------------------------------------------------------


class UnitOfWork(Protocol):
    """Transaction boundary for use cases that modify multiple aggregates.

    Infrastructure adapters implement this to wrap operations in a
    database transaction. The in-memory implementation is a no-op.

    Usage:
        with uow:
            repo.save(entity_a)
            repo.save(entity_b)
            uow.commit()
    """

    def __enter__(self) -> UnitOfWork: ...
    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...


# ---------------------------------------------------------------------------
# Repository ports
# ---------------------------------------------------------------------------


class EventRepository(Protocol):
    def get_by_id(self, event_id: UUID) -> Event | None: ...
    def save(self, event: Event) -> None: ...
    def list_by_status(self, status: str) -> list[Event]: ...


class MarketRepository(Protocol):
    def get_by_id(self, market_id: UUID) -> Market | None: ...
    def save(self, market: Market) -> None: ...
    def list_active(self) -> list[Market]: ...
    def find_by_source_id(self, source_market_id: str) -> Market | None: ...


class PriceSnapshotRepository(Protocol):
    def save(self, snapshot: PriceSnapshot) -> None: ...
    def get_latest(self, market_id: UUID) -> PriceSnapshot | None: ...
    def list_by_market(
        self, market_id: UUID, since: datetime | None = None
    ) -> list[PriceSnapshot]: ...


class ModelEstimateRepository(Protocol):
    def save(self, estimate: ModelEstimate) -> None: ...
    def get_latest(self, market_id: UUID) -> ModelEstimate | None: ...
    def list_by_market(self, market_id: UUID) -> list[ModelEstimate]: ...


class SignalRepository(Protocol):
    def save(self, signal: Signal) -> None: ...
    def list_recent(self, limit: int = 50) -> list[Signal]: ...
    def list_by_market(self, market_id: UUID) -> list[Signal]: ...


class PaperOrderRepository(Protocol):
    def save(self, order: PaperOrder) -> None: ...
    def get_by_id(self, order_id: UUID) -> PaperOrder | None: ...
    def list_by_portfolio(self, portfolio_id: UUID) -> list[PaperOrder]: ...


class PaperFillRepository(Protocol):
    def save(self, fill: PaperFill) -> None: ...
    def list_by_order(self, order_id: UUID) -> list[PaperFill]: ...


class PositionRepository(Protocol):
    def save(self, position: Position) -> None: ...
    def get_by_market(self, portfolio_id: UUID, market_id: UUID) -> Position | None: ...
    def list_by_portfolio(self, portfolio_id: UUID) -> list[Position]: ...


class PortfolioRepository(Protocol):
    def save(self, portfolio: Portfolio) -> None: ...
    def get_by_id(self, portfolio_id: UUID) -> Portfolio | None: ...


class StrategyRunRepository(Protocol):
    def save(self, run: StrategyRun) -> None: ...
    def get_by_id(self, run_id: UUID) -> StrategyRun | None: ...
    def list_all(self) -> list[StrategyRun]: ...


# ---------------------------------------------------------------------------
# Research ports
# ---------------------------------------------------------------------------


class ResearchNoteRepository(Protocol):
    def save(self, note: ResearchNote) -> None: ...
    def list_by_market(self, market_id: UUID) -> list[ResearchNote]: ...
    def list_by_tag(self, tag: str) -> list[ResearchNote]: ...


class WatchlistRepository(Protocol):
    def save(self, watchlist: Watchlist) -> None: ...
    def get_by_id(self, watchlist_id: UUID) -> Watchlist | None: ...
    def list_all(self) -> list[Watchlist]: ...


class WatchlistItemRepository(Protocol):
    def save(self, item: WatchlistItem) -> None: ...
    def list_by_watchlist(self, watchlist_id: UUID) -> list[WatchlistItem]: ...


# ---------------------------------------------------------------------------
# Raw payload repository
# ---------------------------------------------------------------------------


class RawPayloadRepository(Protocol):
    """Stores unmodified provider payloads for audit and replay."""

    def save(self, payload: RawMarketPayload) -> None: ...
    def list_by_provider(self, provider: str) -> list[RawMarketPayload]: ...
    def list_by_market(self, market_id: UUID) -> list[RawMarketPayload]: ...


# ---------------------------------------------------------------------------
# External data provider port
# ---------------------------------------------------------------------------


class ExternalMarketDataProvider(Protocol):
    """Port for fetching market data from an external venue (e.g. Polymarket)."""

    def fetch_active_markets(self) -> list[dict]: ...  # type: ignore[type-arg]
    def fetch_market_detail(self, source_market_id: str) -> dict: ...  # type: ignore[type-arg]
    def fetch_price_snapshot(self, source_market_id: str) -> dict: ...  # type: ignore[type-arg]
