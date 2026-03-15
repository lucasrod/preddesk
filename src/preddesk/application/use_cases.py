"""Application use cases for PredDesk.

Use cases orchestrate domain logic and infrastructure ports. They
contain no business rules themselves — those live in the domain layer.
Use cases are the "glue" that wires together:
- External data providers (via ports)
- Domain entities and value objects
- Repository persistence (via ports)
- Clock for timestamps

Each use case returns a result DTO describing what happened.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol
from uuid import uuid4

from preddesk.domain.backtester import BacktestConfig, Backtester, BacktestResult, Strategy
from preddesk.domain.entities import (
    Event,
    EventStatus,
    Market,
    MarketStatus,
    MarketType,
    ModelEstimate,
    OrderStatus,
    PaperFill,
    PaperOrder,
    Position,
    PriceSnapshot,
    Signal,
    SignalType,
    StrategyRun,
    StrategyRunStatus,
)
from preddesk.domain.paper_broker import PaperBroker
from preddesk.domain.ports import (
    Clock,
    EventRepository,
    ExternalMarketDataProvider,
    MarketRepository,
    ModelEstimateRepository,
    PaperOrderRepository,
    PositionRepository,
    PriceSnapshotRepository,
    SignalRepository,
    StrategyRunRepository,
)
from preddesk.domain.signal_engine import SignalResult
from preddesk.domain.value_objects import MarketSide, OrderSide

if TYPE_CHECKING:
    pass

# ---------------------------------------------------------------------------
# IngestMarkets
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IngestResult:
    """Summary of what the ingestion use case did."""

    markets_ingested: int = 0
    snapshots_saved: int = 0
    errors: int = 0


class IngestMarkets:
    """Fetch markets from an external provider, normalize, and persist.

    Flow:
    1. Call provider.fetch_active_markets().
    2. For each raw market:
       a. Create or find the Event.
       b. Create or find the Market.
       c. Save a PriceSnapshot.
    3. Return a summary.
    """

    def __init__(
        self,
        provider: ExternalMarketDataProvider,
        event_repo: EventRepository,
        market_repo: MarketRepository,
        snapshot_repo: PriceSnapshotRepository,
        clock: Clock,
    ) -> None:
        self._provider = provider
        self._event_repo = event_repo
        self._market_repo = market_repo
        self._snapshot_repo = snapshot_repo
        self._clock = clock

    def execute(self) -> IngestResult:
        raw_markets = self._provider.fetch_active_markets()
        markets_ingested = 0
        snapshots_saved = 0
        errors = 0

        for raw in raw_markets:
            try:
                market = self._process_one(raw)
                if market is not None:
                    markets_ingested += 1
                snapshots_saved += 1
            except Exception:
                errors += 1

        return IngestResult(
            markets_ingested=markets_ingested,
            snapshots_saved=snapshots_saved,
            errors=errors,
        )

    def _process_one(self, raw: dict) -> Market | None:  # type: ignore[type-arg]
        now = self._clock.now()

        # Upsert event
        source_event_id = raw["source_event_id"]
        # Simple approach: use source_market_id to check existence
        source_market_id = raw["source_market_id"]

        existing_market = self._market_repo.find_by_source_id(source_market_id)
        market_is_new = existing_market is None

        if existing_market is not None:
            market = existing_market
        else:
            # Create event
            event = Event(
                event_id=uuid4(),
                source_event_id=source_event_id,
                title=raw.get("event_title", ""),
                category=raw.get("event_category", ""),
                status=EventStatus.OPEN,
                open_time=now,
            )
            self._event_repo.save(event)

            # Create market
            market = Market(
                market_id=uuid4(),
                event_id=event.event_id,
                source_market_id=source_market_id,
                market_type=MarketType(raw.get("market_type", "BINARY")),
                venue=raw.get("venue", "unknown"),
                status=MarketStatus.ACTIVE,
            )
            self._market_repo.save(market)

        # Always save a price snapshot
        snapshot = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=market.market_id,
            captured_at=now,
            best_bid=raw.get("best_bid"),
            best_ask=raw.get("best_ask"),
            last_price=raw.get("last_price"),
            volume=raw.get("volume"),
        )
        self._snapshot_repo.save(snapshot)

        return market if market_is_new else None


# ---------------------------------------------------------------------------
# GenerateEstimate
# ---------------------------------------------------------------------------


class ProbabilityModel(Protocol):
    """Protocol for any probability model that can produce an estimate."""

    @property
    def model_name(self) -> str: ...
    def estimate(self) -> float: ...
    def confidence_interval(self) -> object | None: ...


class GenerateEstimate:
    """Run a probability model on a market and persist the result.

    Flow:
    1. Look up the market.
    2. Run the model to get a point estimate and optional CI.
    3. Create and persist a ModelEstimate entity.
    """

    def __init__(
        self,
        market_repo: MarketRepository,
        estimate_repo: ModelEstimateRepository,
        clock: Clock,
    ) -> None:
        self._market_repo = market_repo
        self._estimate_repo = estimate_repo
        self._clock = clock

    def execute(self, market_id: object, model: ProbabilityModel) -> ModelEstimate | None:
        from uuid import UUID

        mid = market_id if isinstance(market_id, UUID) else UUID(str(market_id))
        market = self._market_repo.get_by_id(mid)
        if market is None:
            return None

        prob = model.estimate()
        ci = model.confidence_interval()
        lower = getattr(ci, "lower", None) if ci is not None else None
        upper = getattr(ci, "upper", None) if ci is not None else None

        estimate = ModelEstimate(
            estimate_id=uuid4(),
            market_id=market.market_id,
            model_name=model.model_name,
            version="1.0",
            estimated_probability=prob,
            lower_bound=lower,
            upper_bound=upper,
            generated_at=self._clock.now(),
        )
        self._estimate_repo.save(estimate)
        return estimate


# ---------------------------------------------------------------------------
# DetectSignal
# ---------------------------------------------------------------------------


def _parse_signal_type(raw: str) -> SignalType:
    """Parse a signal type string, defaulting to EV_GAP."""
    upper = raw.upper()
    valid = {e.value for e in SignalType}
    return SignalType(upper) if upper in valid else SignalType.EV_GAP


class SignalEvaluator(Protocol):
    """Protocol for signal evaluators."""

    def evaluate(
        self, model_prob: float, market_prob: float, **kwargs: object
    ) -> SignalResult: ...


class DetectSignal:
    """Compare model estimate vs market price and emit a Signal if actionable.

    Flow:
    1. Get latest price snapshot → market_prob (mid_price).
    2. Get latest model estimate → model_prob.
    3. Run signal evaluator.
    4. If actionable, persist as a Signal entity.
    """

    def __init__(
        self,
        market_repo: MarketRepository,
        snapshot_repo: PriceSnapshotRepository,
        estimate_repo: ModelEstimateRepository,
        signal_repo: SignalRepository,
        signal_evaluator: SignalEvaluator,
        clock: Clock,
    ) -> None:
        self._market_repo = market_repo
        self._snapshot_repo = snapshot_repo
        self._estimate_repo = estimate_repo
        self._signal_repo = signal_repo
        self._evaluator = signal_evaluator
        self._clock = clock

    def execute(self, market_id: object) -> SignalResult | None:
        from uuid import UUID

        mid = market_id if isinstance(market_id, UUID) else UUID(str(market_id))

        snapshot = self._snapshot_repo.get_latest(mid)
        if snapshot is None or snapshot.mid_price is None:
            return None

        estimate = self._estimate_repo.get_latest(mid)
        if estimate is None:
            return None

        market_prob = snapshot.mid_price
        model_prob = estimate.estimated_probability

        result = self._evaluator.evaluate(model_prob=model_prob, market_prob=market_prob)

        # Persist as a Signal entity
        signal = Signal(
            signal_id=uuid4(),
            market_id=mid,
            estimate_id=estimate.estimate_id,
            signal_type=_parse_signal_type(result.signal_type),
            market_probability=market_prob,
            model_probability=model_prob,
            edge_bps=result.edge_bps,
            expected_value=result.expected_value,
            confidence_score=result.confidence_score,
            rationale=result.rationale,
            generated_at=self._clock.now(),
        )
        self._signal_repo.save(signal)

        return result


# ---------------------------------------------------------------------------
# SimulateOrder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SimulateOrderResult:
    """Result of a simulated order."""

    order: PaperOrder
    fill: PaperFill | None
    position: Position


class SimulateOrder:
    """Submit an order through the paper broker, persist order/fill/position.

    Flow:
    1. Get latest snapshot for the market.
    2. Run the paper broker.
    3. Create PaperOrder (FILLED or REJECTED).
    4. If filled, create PaperFill and update Position.
    """

    def __init__(
        self,
        market_repo: MarketRepository,
        snapshot_repo: PriceSnapshotRepository,
        order_repo: PaperOrderRepository,
        position_repo: PositionRepository,
        broker: PaperBroker,
        clock: Clock,
    ) -> None:
        self._market_repo = market_repo
        self._snapshot_repo = snapshot_repo
        self._order_repo = order_repo
        self._position_repo = position_repo
        self._broker = broker
        self._clock = clock

    def execute(
        self,
        portfolio_id: object,
        market_id: object,
        side: OrderSide,
        quantity: float,
        signal_id: object | None = None,
    ) -> SimulateOrderResult | None:
        from decimal import Decimal
        from uuid import UUID

        mid = market_id if isinstance(market_id, UUID) else UUID(str(market_id))
        pid = portfolio_id if isinstance(portfolio_id, UUID) else UUID(str(portfolio_id))
        sid = None
        if signal_id is not None:
            sid = signal_id if isinstance(signal_id, UUID) else UUID(str(signal_id))

        snapshot = self._snapshot_repo.get_latest(mid)
        if snapshot is None or snapshot.best_bid is None or snapshot.best_ask is None:
            return None

        # Calculate current exposure for risk policy
        existing_positions = self._position_repo.list_by_portfolio(pid)
        current_exposure = sum(p.net_quantity for p in existing_positions)

        fill_result = self._broker.execute(
            side=side,
            quantity=quantity,
            best_bid=snapshot.best_bid,
            best_ask=snapshot.best_ask,
            current_exposure=current_exposure,
        )

        now = self._clock.now()

        if fill_result is None:
            # Risk rejected
            order = PaperOrder(
                paper_order_id=uuid4(),
                portfolio_id=pid,
                market_id=mid,
                side=side,
                quantity=quantity,
                limit_price=snapshot.best_ask if side == OrderSide.BUY else snapshot.best_bid,
                submitted_at=now,
                status=OrderStatus.REJECTED,
                source_signal_id=sid,
            )
            self._order_repo.save(order)
            # Return a dummy position for rejected orders
            existing = self._position_repo.get_by_market(pid, mid)
            pos = existing or Position(
                position_id=uuid4(),
                portfolio_id=pid,
                market_id=mid,
                side=MarketSide.YES if side == OrderSide.BUY else MarketSide.NO,
                net_quantity=0.0,
                avg_cost=0.0,
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                marked_at=now,
            )
            return SimulateOrderResult(order=order, fill=None, position=pos)

        # Filled
        order = PaperOrder(
            paper_order_id=uuid4(),
            portfolio_id=pid,
            market_id=mid,
            side=side,
            quantity=quantity,
            limit_price=fill_result.fill_price,
            submitted_at=now,
            status=OrderStatus.FILLED,
            source_signal_id=sid,
        )
        self._order_repo.save(order)

        fill = PaperFill(
            paper_fill_id=uuid4(),
            paper_order_id=order.paper_order_id,
            fill_price=fill_result.fill_price,
            fill_quantity=fill_result.fill_quantity,
            fee_amount=fill_result.fee_amount,
            slippage_amount=fill_result.slippage_amount,
            filled_at=now,
        )

        # Update position
        existing_pos = self._position_repo.get_by_market(pid, mid)
        if existing_pos is not None:
            new_qty = existing_pos.net_quantity + fill_result.fill_quantity
            old_notional = existing_pos.avg_cost * existing_pos.net_quantity
            new_notional = fill_result.fill_price * fill_result.fill_quantity
            total_cost = old_notional + new_notional
            new_avg = total_cost / new_qty if new_qty > 0 else 0.0
            position = Position(
                position_id=existing_pos.position_id,
                portfolio_id=pid,
                market_id=mid,
                side=MarketSide.YES if side == OrderSide.BUY else MarketSide.NO,
                net_quantity=new_qty,
                avg_cost=new_avg,
                realized_pnl=existing_pos.realized_pnl,
                unrealized_pnl=existing_pos.unrealized_pnl,
                marked_at=now,
            )
        else:
            position = Position(
                position_id=uuid4(),
                portfolio_id=pid,
                market_id=mid,
                side=MarketSide.YES if side == OrderSide.BUY else MarketSide.NO,
                net_quantity=fill_result.fill_quantity,
                avg_cost=fill_result.fill_price,
                realized_pnl=Decimal("0"),
                unrealized_pnl=Decimal("0"),
                marked_at=now,
            )
        self._position_repo.save(position)

        return SimulateOrderResult(order=order, fill=fill, position=position)


# ---------------------------------------------------------------------------
# ExecuteBacktest
# ---------------------------------------------------------------------------


class ExecuteBacktest:
    """Run a backtest on a market's historical snapshots and persist the result.

    Flow:
    1. Look up the market.
    2. Load all price snapshots for that market.
    3. Run the domain backtester.
    4. Persist a StrategyRun entity with summary metrics.
    """

    def __init__(
        self,
        market_repo: MarketRepository,
        snapshot_repo: PriceSnapshotRepository,
        strategy_run_repo: StrategyRunRepository,
        broker: PaperBroker,
        clock: Clock,
    ) -> None:
        self._market_repo = market_repo
        self._snapshot_repo = snapshot_repo
        self._strategy_run_repo = strategy_run_repo
        self._broker = broker
        self._clock = clock

    def execute(
        self,
        market_id: object,
        strategy: Strategy,
        config: BacktestConfig,
    ) -> BacktestResult | None:
        from uuid import UUID

        mid = market_id if isinstance(market_id, UUID) else UUID(str(market_id))
        market = self._market_repo.get_by_id(mid)
        if market is None:
            return None

        snapshots = self._snapshot_repo.list_by_market(mid)
        backtester = Backtester(broker=self._broker)

        now = self._clock.now()
        result = backtester.run(snapshots=snapshots, strategy=strategy, config=config)

        # Persist StrategyRun
        run = StrategyRun(
            strategy_run_id=uuid4(),
            strategy_name=config.strategy_name,
            version=config.version,
            config=config.params,
            started_at=now,
            ended_at=self._clock.now(),
            status=StrategyRunStatus.COMPLETED,
            summary_metrics={
                "total_return": result.metrics.total_return,
                "hit_rate": result.metrics.hit_rate,
                "max_drawdown": result.metrics.max_drawdown,
                "total_trades": result.total_trades,
            },
        )
        self._strategy_run_repo.save(run)

        return result
