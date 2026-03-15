"""REST API for PredDesk.

FastAPI application with endpoints for markets, estimates, signals,
paper trading, and positions. All dependencies are injected via
create_app() to keep the API testable with in-memory fakes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from preddesk.application.research_use_cases import (
    AddNote,
    CreateWatchlist,
    GetMarketResearch,
)
from preddesk.application.use_cases import (
    DetectSignal,
    ExecuteBacktest,
    GenerateEstimate,
    SimulateOrder,
)
from preddesk.domain.backtester import BacktestConfig
from preddesk.domain.paper_broker import (
    BidAskExecution,
    FeeModel,
    PaperBroker,
    RiskPolicy,
    SlippageModel,
)
from preddesk.domain.ports import (
    EventRepository,
    MarketRepository,
    ModelEstimateRepository,
    PaperOrderRepository,
    PortfolioRepository,
    PositionRepository,
    PriceSnapshotRepository,
    ResearchNoteRepository,
    SignalRepository,
    StrategyRunRepository,
    WatchlistItemRepository,
    WatchlistRepository,
)
from preddesk.domain.probability_models import BaseRateModel
from preddesk.domain.signal_engine import ProbabilityGapSignal
from preddesk.domain.value_objects import OrderSide

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class PaperOrderRequest(BaseModel):
    portfolio_id: UUID
    market_id: UUID
    side: str  # "BUY" or "SELL"
    quantity: float
    signal_id: UUID | None = None


class RunSignalRequest(BaseModel):
    market_id: UUID


class RunBacktestRequest(BaseModel):
    market_id: UUID
    strategy_name: str
    version: str = "1.0"


class CreateNoteRequest(BaseModel):
    market_id: UUID
    content: str
    tags: list[str] = []
    hypothesis: str | None = None


class CreateWatchlistRequest(BaseModel):
    name: str
    description: str | None = None


class RunEstimateRequest(BaseModel):
    model_name: str
    successes: int
    total: int


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------


class _WallClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


def create_app(
    market_repo: MarketRepository,
    event_repo: EventRepository,
    snapshot_repo: PriceSnapshotRepository,
    estimate_repo: ModelEstimateRepository,
    signal_repo: SignalRepository,
    order_repo: PaperOrderRepository,
    position_repo: PositionRepository,
    portfolio_repo: PortfolioRepository | None = None,
    strategy_run_repo: StrategyRunRepository | None = None,
    note_repo: ResearchNoteRepository | None = None,
    watchlist_repo: WatchlistRepository | None = None,
    watchlist_item_repo: WatchlistItemRepository | None = None,
) -> FastAPI:
    """Create a FastAPI app with injected dependencies."""
    app = FastAPI(title="PredDesk", version="0.1.0")

    clock = _WallClock()
    default_broker = PaperBroker(
        execution_model=BidAskExecution(),
        slippage_model=SlippageModel(slippage_bps=50.0),
        fee_model=FeeModel(fee_rate=0.02),
        risk_policy=RiskPolicy(max_position_size=100.0, max_portfolio_exposure=10000.0),
    )

    # -- Health ---------------------------------------------------------------

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # -- Markets --------------------------------------------------------------

    @app.get("/markets")
    def list_markets() -> list[dict]:  # type: ignore[type-arg]
        markets = market_repo.list_active()
        return [m.model_dump(mode="json") for m in markets]

    @app.get("/markets/{market_id}")
    def get_market(market_id: UUID) -> dict:  # type: ignore[type-arg]
        market = market_repo.get_by_id(market_id)
        if market is None:
            raise HTTPException(status_code=404, detail="Market not found")
        return market.model_dump(mode="json")

    @app.get("/markets/{market_id}/snapshots")
    def get_market_snapshots(market_id: UUID) -> list[dict]:  # type: ignore[type-arg]
        snapshots = snapshot_repo.list_by_market(market_id)
        return [s.model_dump(mode="json") for s in snapshots]

    @app.get("/markets/{market_id}/estimates")
    def get_market_estimates(market_id: UUID) -> list[dict]:  # type: ignore[type-arg]
        estimates = estimate_repo.list_by_market(market_id)
        return [e.model_dump(mode="json") for e in estimates]

    # -- POST: Run Estimate ---------------------------------------------------

    @app.post("/markets/{market_id}/estimates/run")
    def run_estimate(market_id: UUID, body: RunEstimateRequest) -> dict:  # type: ignore[type-arg]
        model = BaseRateModel(successes=body.successes, total=body.total)
        uc = GenerateEstimate(
            market_repo=market_repo,
            estimate_repo=estimate_repo,
            clock=clock,
        )
        result = uc.execute(market_id=market_id, model=model)
        if result is None:
            raise HTTPException(status_code=404, detail="Market not found")
        return result.model_dump(mode="json")

    # -- Signals --------------------------------------------------------------

    @app.get("/signals")
    def list_signals() -> list[dict]:  # type: ignore[type-arg]
        signals = signal_repo.list_recent(limit=50)
        return [s.model_dump(mode="json") for s in signals]

    @app.post("/signals/run")
    def run_signal(body: RunSignalRequest) -> dict:  # type: ignore[type-arg]
        uc = DetectSignal(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            estimate_repo=estimate_repo,
            signal_repo=signal_repo,
            signal_evaluator=ProbabilityGapSignal(),
            clock=clock,
        )
        result = uc.execute(market_id=body.market_id)
        if result is None:
            raise HTTPException(status_code=404, detail="No snapshot or estimate for market")
        return {
            "signal_type": result.signal_type,
            "edge_bps": result.edge_bps,
            "is_actionable": result.is_actionable,
            "rationale": result.rationale,
            "expected_value": result.expected_value,
            "confidence_score": result.confidence_score,
        }

    # -- Paper Orders ---------------------------------------------------------

    @app.get("/paper-orders")
    def list_paper_orders(portfolio_id: UUID | None = None) -> list[dict]:  # type: ignore[type-arg]
        orders = order_repo.list_by_portfolio(portfolio_id) if portfolio_id is not None else []
        return [o.model_dump(mode="json") for o in orders]

    @app.post("/paper-orders")
    def submit_paper_order(body: PaperOrderRequest) -> dict:  # type: ignore[type-arg]
        uc = SimulateOrder(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            order_repo=order_repo,
            position_repo=position_repo,
            broker=default_broker,
            clock=clock,
        )
        side = OrderSide(body.side)
        result = uc.execute(
            portfolio_id=body.portfolio_id,
            market_id=body.market_id,
            side=side,
            quantity=body.quantity,
            signal_id=body.signal_id,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="No snapshot available for market")
        return {
            "order": result.order.model_dump(mode="json"),
            "fill": result.fill.model_dump(mode="json") if result.fill else None,
            "position": result.position.model_dump(mode="json"),
        }

    # -- Positions ------------------------------------------------------------

    @app.get("/positions")
    def list_positions(portfolio_id: UUID | None = None) -> list[dict]:  # type: ignore[type-arg]
        if portfolio_id is not None:
            positions = position_repo.list_by_portfolio(portfolio_id)
        else:
            positions = []
        return [p.model_dump(mode="json") for p in positions]

    # -- Portfolio -------------------------------------------------------------

    @app.get("/portfolio")
    def get_portfolio(portfolio_id: UUID | None = None) -> dict:  # type: ignore[type-arg]
        if portfolio_id is None or portfolio_repo is None:
            return {"positions": [], "portfolio": None}
        portfolio = portfolio_repo.get_by_id(portfolio_id)
        positions = position_repo.list_by_portfolio(portfolio_id)
        return {
            "portfolio": portfolio.model_dump(mode="json") if portfolio else None,
            "positions": [p.model_dump(mode="json") for p in positions],
        }

    # -- Backtests -------------------------------------------------------------

    @app.post("/backtests/run")
    def run_backtest(body: RunBacktestRequest) -> dict:  # type: ignore[type-arg]
        if strategy_run_repo is None:
            raise HTTPException(status_code=501, detail="Backtest storage not configured")

        from preddesk.domain.value_objects import OrderSide as OS

        class AlwaysBuyStrategy:
            """Default strategy for API-driven backtests."""

            def on_snapshot(
                self, snapshot: object, position_qty: float
            ) -> tuple[OS, float] | None:
                if position_qty == 0.0:
                    return (OS.BUY, 1.0)
                return None

        uc = ExecuteBacktest(
            market_repo=market_repo,
            snapshot_repo=snapshot_repo,
            strategy_run_repo=strategy_run_repo,
            broker=default_broker,
            clock=clock,
        )
        config = BacktestConfig(
            strategy_name=body.strategy_name,
            version=body.version,
        )
        result = uc.execute(
            market_id=body.market_id,
            strategy=AlwaysBuyStrategy(),
            config=config,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Market not found")
        return {
            "total_trades": result.total_trades,
            "metrics": {
                "total_return": result.metrics.total_return,
                "hit_rate": result.metrics.hit_rate,
                "max_drawdown": result.metrics.max_drawdown,
                "avg_edge_captured": result.metrics.avg_edge_captured,
                "turnover": result.metrics.turnover,
            },
        }

    @app.get("/backtests/{strategy_run_id}")
    def get_backtest(strategy_run_id: UUID) -> dict:  # type: ignore[type-arg]
        if strategy_run_repo is None:
            raise HTTPException(status_code=501, detail="Backtest storage not configured")
        run = strategy_run_repo.get_by_id(strategy_run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Strategy run not found")
        return run.model_dump(mode="json")

    # -- Research: Notes -------------------------------------------------------

    @app.post("/notes")
    def post_note(body: CreateNoteRequest) -> dict:  # type: ignore[type-arg]
        if note_repo is None:
            raise HTTPException(status_code=501, detail="Research notes not configured")
        uc = AddNote(note_repo=note_repo, clock=clock)
        result = uc.execute(
            market_id=body.market_id,
            content=body.content,
            tags=body.tags,
            hypothesis=body.hypothesis,
        )
        return result.model_dump(mode="json")

    # -- Research: Watchlists --------------------------------------------------

    @app.post("/watchlists")
    def post_watchlist(body: CreateWatchlistRequest) -> dict:  # type: ignore[type-arg]
        if watchlist_repo is None:
            raise HTTPException(status_code=501, detail="Watchlists not configured")
        uc = CreateWatchlist(watchlist_repo=watchlist_repo, clock=clock)
        result = uc.execute(name=body.name, description=body.description)
        return result.model_dump(mode="json")

    # -- Research: Market research view ----------------------------------------

    @app.get("/research/markets/{market_id}")
    def get_market_research(market_id: UUID) -> dict:  # type: ignore[type-arg]
        if note_repo is None or watchlist_item_repo is None:
            raise HTTPException(status_code=501, detail="Research not configured")
        uc = GetMarketResearch(note_repo=note_repo, item_repo=watchlist_item_repo)
        result = uc.execute(market_id=market_id)
        return {
            "notes": [n.model_dump(mode="json") for n in result["notes"]],
            "watchlist_items": [i.model_dump(mode="json") for i in result["watchlist_items"]],
        }

    return app
