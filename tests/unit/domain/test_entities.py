"""Unit tests for domain entities.

Entities represent the core business objects of the prediction-market
domain. Unlike value objects, entities carry identity (IDs) and may
have lifecycle states.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from preddesk.domain.entities import (
    Event,
    EventStatus,
    Market,
    MarketStatus,
    MarketType,
    ModelEstimate,
    OrderStatus,
    Outcome,
    PaperFill,
    PaperOrder,
    Portfolio,
    Position,
    PriceSnapshot,
    RawMarketPayload,
    Signal,
    SignalType,
    StrategyRun,
    StrategyRunStatus,
)
from preddesk.domain.value_objects import MarketSide, OrderSide

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------


class TestEvent:
    def test_creation(self):
        e = Event(
            event_id=uuid4(),
            source_event_id="poly-123",
            title="US Presidential Election 2028",
            category="politics",
            status=EventStatus.OPEN,
            open_time=NOW,
        )
        assert e.title == "US Presidential Election 2028"
        assert e.status == EventStatus.OPEN

    def test_status_values(self):
        assert EventStatus.OPEN.value == "OPEN"
        assert EventStatus.CLOSED.value == "CLOSED"
        assert EventStatus.RESOLVED.value == "RESOLVED"


# ---------------------------------------------------------------------------
# Market
# ---------------------------------------------------------------------------


class TestMarket:
    def test_creation(self):
        m = Market(
            market_id=uuid4(),
            event_id=uuid4(),
            source_market_id="poly-mkt-456",
            market_type=MarketType.BINARY,
            venue="polymarket",
            status=MarketStatus.ACTIVE,
        )
        assert m.venue == "polymarket"
        assert m.market_type == MarketType.BINARY

    def test_default_currency(self):
        m = Market(
            market_id=uuid4(),
            event_id=uuid4(),
            source_market_id="x",
            market_type=MarketType.BINARY,
            venue="polymarket",
            status=MarketStatus.ACTIVE,
        )
        assert m.quote_currency == "USDC"


# ---------------------------------------------------------------------------
# Outcome
# ---------------------------------------------------------------------------


class TestOutcome:
    def test_creation(self):
        o = Outcome(
            outcome_id=uuid4(),
            market_id=uuid4(),
            name="Yes",
            side=MarketSide.YES,
        )
        assert o.side == MarketSide.YES


# ---------------------------------------------------------------------------
# PriceSnapshot
# ---------------------------------------------------------------------------


class TestPriceSnapshot:
    def test_mid_price_calculation(self):
        """Mid price is the average of best bid and best ask.
        This is a standard microstructure convention."""
        snap = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=uuid4(),
            captured_at=NOW,
            best_bid=0.55,
            best_ask=0.60,
        )
        assert snap.mid_price == pytest.approx(0.575)

    def test_mid_price_none_when_missing_bid(self):
        snap = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=uuid4(),
            captured_at=NOW,
            best_bid=None,
            best_ask=0.60,
        )
        assert snap.mid_price is None

    def test_mid_price_none_when_missing_ask(self):
        snap = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=uuid4(),
            captured_at=NOW,
            best_bid=0.55,
            best_ask=None,
        )
        assert snap.mid_price is None

    def test_spread(self):
        snap = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=uuid4(),
            captured_at=NOW,
            best_bid=0.55,
            best_ask=0.60,
        )
        assert snap.spread == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# ModelEstimate
# ---------------------------------------------------------------------------


class TestModelEstimate:
    def test_creation(self):
        est = ModelEstimate(
            estimate_id=uuid4(),
            market_id=uuid4(),
            model_name="base_rate_v1",
            version="1.0",
            estimated_probability=0.70,
            generated_at=NOW,
        )
        assert est.estimated_probability == pytest.approx(0.70)

    def test_rejects_invalid_probability(self):
        with pytest.raises(ValueError):
            ModelEstimate(
                estimate_id=uuid4(),
                market_id=uuid4(),
                model_name="test",
                version="1.0",
                estimated_probability=1.5,
                generated_at=NOW,
            )

    def test_optional_bounds(self):
        est = ModelEstimate(
            estimate_id=uuid4(),
            market_id=uuid4(),
            model_name="bayes_v1",
            version="1.0",
            estimated_probability=0.60,
            lower_bound=0.45,
            upper_bound=0.75,
            generated_at=NOW,
        )
        assert est.lower_bound == pytest.approx(0.45)
        assert est.upper_bound == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Signal
# ---------------------------------------------------------------------------


class TestSignal:
    def test_creation(self):
        sig = Signal(
            signal_id=uuid4(),
            market_id=uuid4(),
            signal_type=SignalType.EV_GAP,
            market_probability=0.55,
            model_probability=0.70,
            edge_bps=1500.0,
            generated_at=NOW,
        )
        assert sig.edge_bps == pytest.approx(1500.0)

    def test_signal_types(self):
        assert SignalType.EV_GAP.value == "EV_GAP"
        assert SignalType.THRESHOLD.value == "THRESHOLD"
        assert SignalType.CONFIDENCE_WEIGHTED.value == "CONFIDENCE_WEIGHTED"


# ---------------------------------------------------------------------------
# PaperOrder & PaperFill
# ---------------------------------------------------------------------------


class TestPaperOrder:
    def test_creation(self):
        order = PaperOrder(
            paper_order_id=uuid4(),
            portfolio_id=uuid4(),
            market_id=uuid4(),
            side=OrderSide.BUY,
            quantity=10.0,
            limit_price=0.60,
            submitted_at=NOW,
            status=OrderStatus.PENDING,
        )
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.PENDING


class TestPaperFill:
    def test_creation(self):
        fill = PaperFill(
            paper_fill_id=uuid4(),
            paper_order_id=uuid4(),
            fill_price=0.61,
            fill_quantity=10.0,
            fee_amount=Decimal("0.10"),
            slippage_amount=Decimal("0.01"),
            filled_at=NOW,
        )
        assert fill.fill_price == pytest.approx(0.61)


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


class TestPosition:
    def test_creation(self):
        pos = Position(
            position_id=uuid4(),
            portfolio_id=uuid4(),
            market_id=uuid4(),
            side=MarketSide.YES,
            net_quantity=10.0,
            avg_cost=0.60,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            marked_at=NOW,
        )
        assert pos.net_quantity == 10.0

    def test_mark_to_market(self):
        """Unrealized PnL for a YES position:
        (current_price - avg_cost) * quantity.
        This is a standard mark-to-market convention."""
        pos = Position(
            position_id=uuid4(),
            portfolio_id=uuid4(),
            market_id=uuid4(),
            side=MarketSide.YES,
            net_quantity=10.0,
            avg_cost=0.60,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            marked_at=NOW,
        )
        unrealized = pos.compute_unrealized_pnl(current_price=0.75)
        assert unrealized == pytest.approx(1.50)  # (0.75 - 0.60) * 10


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


class TestPortfolio:
    def test_creation(self):
        pf = Portfolio(
            portfolio_id=uuid4(),
            name="Research Paper Portfolio",
            created_at=NOW,
        )
        assert pf.name == "Research Paper Portfolio"


# ---------------------------------------------------------------------------
# StrategyRun
# ---------------------------------------------------------------------------


class TestStrategyRun:
    def test_creation(self):
        run = StrategyRun(
            strategy_run_id=uuid4(),
            strategy_name="ev_gap_v1",
            version="1.0",
            config={"threshold_bps": 500},
            started_at=NOW,
            status=StrategyRunStatus.RUNNING,
        )
        assert run.status == StrategyRunStatus.RUNNING


# ---------------------------------------------------------------------------
# RawMarketPayload
# ---------------------------------------------------------------------------


class TestRawMarketPayload:
    """Raw payloads store unmodified provider responses for audit and replay."""

    def test_creation(self):
        payload = RawMarketPayload(
            payload_id=uuid4(),
            provider="polymarket",
            fetched_at=NOW,
            raw_data={"slug": "will-it-rain", "yes_price": 0.65},
        )
        assert payload.provider == "polymarket"
        assert payload.raw_data["slug"] == "will-it-rain"

    def test_with_market_reference(self):
        mid = uuid4()
        payload = RawMarketPayload(
            payload_id=uuid4(),
            provider="polymarket",
            fetched_at=NOW,
            raw_data={"price": 0.5},
            market_id=mid,
        )
        assert payload.market_id == mid

    def test_immutable(self):
        payload = RawMarketPayload(
            payload_id=uuid4(),
            provider="polymarket",
            fetched_at=NOW,
            raw_data={},
        )
        with pytest.raises(ValidationError):
            payload.provider = "metaculus"  # type: ignore[misc]
