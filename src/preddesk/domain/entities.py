"""Domain entities for PredDesk.

Entities carry identity (UUIDs) and represent the core business objects
of the prediction-market domain: events, markets, snapshots, estimates,
signals, orders, positions, and strategy runs.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator

from preddesk.domain.value_objects import MarketSide, OrderSide

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EventStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    RESOLVED = "RESOLVED"


class MarketStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    RESOLVED = "RESOLVED"
    CANCELLED = "CANCELLED"


class MarketType(StrEnum):
    BINARY = "BINARY"
    CATEGORICAL = "CATEGORICAL"


class SignalType(StrEnum):
    EV_GAP = "EV_GAP"
    THRESHOLD = "THRESHOLD"
    CONFIDENCE_WEIGHTED = "CONFIDENCE_WEIGHTED"


class OrderStatus(StrEnum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class StrategyRunStatus(StrEnum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class Event(BaseModel, frozen=True):
    """A real-world event that one or more markets are based on."""

    event_id: UUID
    source_event_id: str
    title: str
    category: str
    status: EventStatus
    open_time: datetime
    description: str | None = None
    close_time: datetime | None = None
    resolve_time: datetime | None = None
    metadata: dict[str, Any] | None = None


class Market(BaseModel, frozen=True):
    """A tradable instrument linked to an Event."""

    market_id: UUID
    event_id: UUID
    source_market_id: str
    market_type: MarketType
    venue: str
    status: MarketStatus
    quote_currency: str = "USDC"
    rules_text: str | None = None
    resolution_source: str | None = None
    metadata: dict[str, Any] | None = None


class Outcome(BaseModel, frozen=True):
    """One side (YES/NO) of a binary market."""

    outcome_id: UUID
    market_id: UUID
    name: str
    side: MarketSide


class PriceSnapshot(BaseModel, frozen=True):
    """Point-in-time observable state of a market.

    The mid_price is computed as (best_bid + best_ask) / 2, a standard
    microstructure convention for estimating fair value.
    """

    snapshot_id: UUID
    market_id: UUID
    captured_at: datetime
    best_bid: float | None = None
    best_ask: float | None = None
    last_price: float | None = None
    volume: float | None = None
    liquidity_hint: float | None = None
    raw_payload_ref: str | None = None

    @property
    def mid_price(self) -> float | None:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2.0
        return None

    @property
    def spread(self) -> float | None:
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None


class ModelEstimate(BaseModel, frozen=True):
    """A probability estimate produced by a model."""

    estimate_id: UUID
    market_id: UUID
    model_name: str
    version: str
    estimated_probability: float
    generated_at: datetime
    lower_bound: float | None = None
    upper_bound: float | None = None
    inputs_hash: str | None = None
    explanation: str | None = None

    @field_validator("estimated_probability")
    @classmethod
    def _must_be_valid_probability(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            msg = f"estimated_probability must be in [0, 1], got {v}"
            raise ValueError(msg)
        return v


class Signal(BaseModel, frozen=True):
    """A detected opportunity — difference between model and market."""

    signal_id: UUID
    market_id: UUID
    signal_type: SignalType
    market_probability: float
    model_probability: float
    edge_bps: float
    generated_at: datetime
    estimate_id: UUID | None = None
    expected_value: float | None = None
    confidence_score: float | None = None
    rationale: str | None = None


class PaperOrder(BaseModel, frozen=True):
    """A simulated order."""

    paper_order_id: UUID
    portfolio_id: UUID
    market_id: UUID
    side: OrderSide
    quantity: float
    limit_price: float
    submitted_at: datetime
    status: OrderStatus
    source_signal_id: UUID | None = None


class PaperFill(BaseModel, frozen=True):
    """A simulated execution with fees and slippage."""

    paper_fill_id: UUID
    paper_order_id: UUID
    fill_price: float
    fill_quantity: float
    fee_amount: Decimal
    slippage_amount: Decimal
    filled_at: datetime


class Position(BaseModel, frozen=True):
    """Aggregated position in a single market."""

    position_id: UUID
    portfolio_id: UUID
    market_id: UUID
    side: MarketSide
    net_quantity: float
    avg_cost: float
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    marked_at: datetime

    def compute_unrealized_pnl(self, current_price: float) -> float:
        """Mark-to-market: (current_price - avg_cost) * net_quantity.

        For a YES position, if current price > avg cost, the position
        is in profit. This is the standard linear PnL for a long position.
        """
        return (current_price - self.avg_cost) * self.net_quantity


class Portfolio(BaseModel, frozen=True):
    """A collection of positions."""

    portfolio_id: UUID
    name: str
    created_at: datetime


class StrategyRun(BaseModel, frozen=True):
    """Metadata for a backtest or strategy execution."""

    strategy_run_id: UUID
    strategy_name: str
    version: str
    config: dict[str, Any]
    started_at: datetime
    status: StrategyRunStatus
    ended_at: datetime | None = None
    summary_metrics: dict[str, Any] | None = None


class RawMarketPayload(BaseModel, frozen=True):
    """Unmodified payload from an external provider.

    Stored for audit, replay, and debugging. The raw_data dict preserves
    the provider's JSON exactly as received. An optional market_id links
    the payload to its canonical market after normalization.
    """

    payload_id: UUID
    provider: str
    fetched_at: datetime
    raw_data: dict[str, Any]
    market_id: UUID | None = None
