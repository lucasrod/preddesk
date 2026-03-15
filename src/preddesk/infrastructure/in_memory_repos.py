"""In-memory repository implementations for testing.

These repos store data in plain dicts/lists and implement the domain
port protocols. They are used by the application layer tests to avoid
any database dependency.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from preddesk.domain.entities import (
    Event,
    Market,
    MarketStatus,
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


class InMemoryEventRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Event] = {}

    def get_by_id(self, event_id: UUID) -> Event | None:
        return self._store.get(event_id)

    def save(self, event: Event) -> None:
        self._store[event.event_id] = event

    def list_by_status(self, status: str) -> list[Event]:
        return [e for e in self._store.values() if e.status.value == status]


class InMemoryMarketRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Market] = {}

    def get_by_id(self, market_id: UUID) -> Market | None:
        return self._store.get(market_id)

    def save(self, market: Market) -> None:
        self._store[market.market_id] = market

    def list_active(self) -> list[Market]:
        return [m for m in self._store.values() if m.status == MarketStatus.ACTIVE]

    def find_by_source_id(self, source_market_id: str) -> Market | None:
        for m in self._store.values():
            if m.source_market_id == source_market_id:
                return m
        return None


class InMemoryPriceSnapshotRepository:
    def __init__(self) -> None:
        self._store: list[PriceSnapshot] = []

    def save(self, snapshot: PriceSnapshot) -> None:
        self._store.append(snapshot)

    def get_latest(self, market_id: UUID) -> PriceSnapshot | None:
        relevant = [s for s in self._store if s.market_id == market_id]
        if not relevant:
            return None
        return max(relevant, key=lambda s: s.captured_at)

    def list_by_market(
        self, market_id: UUID, since: datetime | None = None
    ) -> list[PriceSnapshot]:
        result = [s for s in self._store if s.market_id == market_id]
        if since is not None:
            result = [s for s in result if s.captured_at >= since]
        return sorted(result, key=lambda s: s.captured_at)


class InMemoryModelEstimateRepository:
    def __init__(self) -> None:
        self._store: list[ModelEstimate] = []

    def save(self, estimate: ModelEstimate) -> None:
        self._store.append(estimate)

    def get_latest(self, market_id: UUID) -> ModelEstimate | None:
        relevant = [e for e in self._store if e.market_id == market_id]
        if not relevant:
            return None
        return max(relevant, key=lambda e: e.generated_at)

    def list_by_market(self, market_id: UUID) -> list[ModelEstimate]:
        return [e for e in self._store if e.market_id == market_id]


class InMemorySignalRepository:
    def __init__(self) -> None:
        self._store: list[Signal] = []

    def save(self, signal: Signal) -> None:
        self._store.append(signal)

    def list_recent(self, limit: int = 50) -> list[Signal]:
        sorted_signals = sorted(self._store, key=lambda s: s.generated_at, reverse=True)
        return sorted_signals[:limit]

    def list_by_market(self, market_id: UUID) -> list[Signal]:
        return [s for s in self._store if s.market_id == market_id]


class InMemoryPaperOrderRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, PaperOrder] = {}

    def save(self, order: PaperOrder) -> None:
        self._store[order.paper_order_id] = order

    def get_by_id(self, order_id: UUID) -> PaperOrder | None:
        return self._store.get(order_id)

    def list_by_portfolio(self, portfolio_id: UUID) -> list[PaperOrder]:
        return [o for o in self._store.values() if o.portfolio_id == portfolio_id]


class InMemoryPositionRepository:
    def __init__(self) -> None:
        self._store: dict[tuple[UUID, UUID], Position] = {}

    def save(self, position: Position) -> None:
        self._store[(position.portfolio_id, position.market_id)] = position

    def get_by_market(self, portfolio_id: UUID, market_id: UUID) -> Position | None:
        return self._store.get((portfolio_id, market_id))

    def list_by_portfolio(self, portfolio_id: UUID) -> list[Position]:
        return [p for p in self._store.values() if p.portfolio_id == portfolio_id]


class InMemoryPaperFillRepository:
    def __init__(self) -> None:
        self._store: list[PaperFill] = []

    def save(self, fill: PaperFill) -> None:
        self._store.append(fill)

    def list_by_order(self, order_id: UUID) -> list[PaperFill]:
        return [f for f in self._store if f.paper_order_id == order_id]


class InMemoryPortfolioRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Portfolio] = {}

    def save(self, portfolio: Portfolio) -> None:
        self._store[portfolio.portfolio_id] = portfolio

    def get_by_id(self, portfolio_id: UUID) -> Portfolio | None:
        return self._store.get(portfolio_id)


class InMemoryStrategyRunRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, StrategyRun] = {}

    def save(self, run: StrategyRun) -> None:
        self._store[run.strategy_run_id] = run

    def get_by_id(self, run_id: UUID) -> StrategyRun | None:
        return self._store.get(run_id)

    def list_all(self) -> list[StrategyRun]:
        return list(self._store.values())


class InMemoryResearchNoteRepository:
    def __init__(self) -> None:
        self._store: list[ResearchNote] = []

    def save(self, note: ResearchNote) -> None:
        self._store.append(note)

    def list_by_market(self, market_id: UUID) -> list[ResearchNote]:
        return [n for n in self._store if n.market_id == market_id]

    def list_by_tag(self, tag: str) -> list[ResearchNote]:
        return [n for n in self._store if tag in n.tags]


class InMemoryWatchlistRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Watchlist] = {}

    def save(self, watchlist: Watchlist) -> None:
        self._store[watchlist.watchlist_id] = watchlist

    def get_by_id(self, watchlist_id: UUID) -> Watchlist | None:
        return self._store.get(watchlist_id)

    def list_all(self) -> list[Watchlist]:
        return list(self._store.values())


class InMemoryWatchlistItemRepository:
    def __init__(self) -> None:
        self._store: list[WatchlistItem] = []

    def save(self, item: WatchlistItem) -> None:
        self._store.append(item)

    def list_by_watchlist(self, watchlist_id: UUID) -> list[WatchlistItem]:
        return [i for i in self._store if i.watchlist_id == watchlist_id]


class InMemoryRawPayloadRepository:
    def __init__(self) -> None:
        self._store: list[RawMarketPayload] = []

    def save(self, payload: RawMarketPayload) -> None:
        self._store.append(payload)

    def list_by_provider(self, provider: str) -> list[RawMarketPayload]:
        return [p for p in self._store if p.provider == provider]

    def list_by_market(self, market_id: UUID) -> list[RawMarketPayload]:
        return [p for p in self._store if p.market_id == market_id]
