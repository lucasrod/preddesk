"""Unit tests for the paper broker.

The paper broker simulates trade execution with configurable fees,
slippage, and position sizing. It must be:
1. Deterministic — same inputs always produce the same fill.
2. Explainable — every fill includes a breakdown of price, fees, slippage.
3. Conservative — no over-sizing, no impossible fills.

The broker does NOT interact with any external system. It operates
purely on domain types and configuration.

Execution models:
- MidPriceExecution: fills at mid-price (naive baseline).
- BidAskExecution: buys at ask, sells at bid (realistic-lite).
Both support configurable slippage and fee models.
"""

from decimal import Decimal

import pytest

from preddesk.domain.paper_broker import (
    BidAskExecution,
    FeeModel,
    MidPriceExecution,
    PaperBroker,
    PositionSizer,
    RiskPolicy,
    SlippageModel,
)
from preddesk.domain.value_objects import OrderSide

# ---------------------------------------------------------------------------
# SlippageModel
# ---------------------------------------------------------------------------


class TestSlippageModel:
    """Slippage represents the adverse price movement between the intended
    fill price and the actual fill price. In a paper broker, this is a
    configurable penalty to keep simulations honest.

    slippage_amount = base_price * slippage_bps / 10_000

    For BUY: fill_price = base_price + slippage (worse for buyer)
    For SELL: fill_price = base_price - slippage (worse for seller)
    """

    def test_zero_slippage(self):
        model = SlippageModel(slippage_bps=0.0)
        assert model.apply(base_price=0.60, side=OrderSide.BUY) == pytest.approx(0.60)

    def test_buy_slippage_increases_price(self):
        model = SlippageModel(slippage_bps=50.0)
        # 50 bps on 0.60 = 0.003
        result = model.apply(base_price=0.60, side=OrderSide.BUY)
        assert result == pytest.approx(0.603)

    def test_sell_slippage_decreases_price(self):
        model = SlippageModel(slippage_bps=50.0)
        result = model.apply(base_price=0.60, side=OrderSide.SELL)
        assert result == pytest.approx(0.597)


# ---------------------------------------------------------------------------
# FeeModel
# ---------------------------------------------------------------------------


class TestFeeModel:
    """Fees are charged as a percentage of notional value.

    fee = quantity * fill_price * fee_rate

    For prediction markets, typical fees are 1-5% of notional.
    """

    def test_zero_fee(self):
        model = FeeModel(fee_rate=0.0)
        assert model.compute(quantity=10.0, fill_price=0.60) == Decimal("0")

    def test_percentage_fee(self):
        model = FeeModel(fee_rate=0.02)
        # 10 * 0.60 * 0.02 = 0.12
        fee = model.compute(quantity=10.0, fill_price=0.60)
        assert fee == pytest.approx(Decimal("0.12"), abs=Decimal("0.001"))

    def test_fee_scales_with_quantity(self):
        model = FeeModel(fee_rate=0.02)
        fee_10 = model.compute(quantity=10.0, fill_price=0.60)
        fee_20 = model.compute(quantity=20.0, fill_price=0.60)
        assert float(fee_20) == pytest.approx(float(fee_10) * 2)


# ---------------------------------------------------------------------------
# Execution Models
# ---------------------------------------------------------------------------


class TestMidPriceExecution:
    """Fills at mid-price. Simplest model, useful for backtesting baselines.
    Not realistic — ignores the spread entirely."""

    def test_buy_at_mid(self):
        exec_model = MidPriceExecution()
        price = exec_model.fill_price(side=OrderSide.BUY, best_bid=0.55, best_ask=0.60)
        assert price == pytest.approx(0.575)

    def test_sell_at_mid(self):
        exec_model = MidPriceExecution()
        price = exec_model.fill_price(side=OrderSide.SELL, best_bid=0.55, best_ask=0.60)
        assert price == pytest.approx(0.575)


class TestBidAskExecution:
    """BUY fills at ask (worst price for buyer).
    SELL fills at bid (worst price for seller).
    This is the realistic-lite model for Phase 1."""

    def test_buy_at_ask(self):
        exec_model = BidAskExecution()
        price = exec_model.fill_price(side=OrderSide.BUY, best_bid=0.55, best_ask=0.60)
        assert price == pytest.approx(0.60)

    def test_sell_at_bid(self):
        exec_model = BidAskExecution()
        price = exec_model.fill_price(side=OrderSide.SELL, best_bid=0.55, best_ask=0.60)
        assert price == pytest.approx(0.55)


# ---------------------------------------------------------------------------
# PositionSizer
# ---------------------------------------------------------------------------


class TestPositionSizer:
    """Position sizing determines how many contracts to buy/sell.

    Fixed unit: always buy N contracts.
    Fractional Kelly: uses Kelly criterion output as fraction of bankroll.
    """

    def test_fixed_unit(self):
        sizer = PositionSizer.fixed(units=10.0)
        assert sizer.compute(bankroll=1000.0, price=0.60) == pytest.approx(10.0)

    def test_fixed_dollar(self):
        """Risk $100 at price 0.60 → buy 100/0.60 ≈ 166.67 contracts."""
        sizer = PositionSizer.fixed_dollar(risk_amount=100.0)
        assert sizer.compute(bankroll=1000.0, price=0.60) == pytest.approx(100.0 / 0.60, rel=1e-2)

    def test_kelly_fraction(self):
        """Kelly fraction 0.10 of $1000 bankroll at price 0.60
        → 0.10 * 1000 / 0.60 ≈ 166.67 contracts."""
        sizer = PositionSizer.kelly(kelly_fraction=0.10)
        result = sizer.compute(bankroll=1000.0, price=0.60)
        assert result == pytest.approx(0.10 * 1000.0 / 0.60, rel=1e-2)

    def test_kelly_respects_bankroll(self):
        """Position size scales with bankroll."""
        sizer = PositionSizer.kelly(kelly_fraction=0.10)
        small = sizer.compute(bankroll=500.0, price=0.60)
        large = sizer.compute(bankroll=1000.0, price=0.60)
        assert large > small


# ---------------------------------------------------------------------------
# RiskPolicy
# ---------------------------------------------------------------------------


class TestRiskPolicy:
    """Risk policies validate orders before execution.

    - Max position size per market.
    - Max portfolio exposure.
    """

    def test_allows_within_limit(self):
        policy = RiskPolicy(max_position_size=100.0, max_portfolio_exposure=1000.0)
        assert policy.validate(quantity=50.0, current_exposure=500.0) is True

    def test_rejects_exceeding_position_limit(self):
        policy = RiskPolicy(max_position_size=100.0, max_portfolio_exposure=1000.0)
        assert policy.validate(quantity=150.0, current_exposure=500.0) is False

    def test_rejects_exceeding_portfolio_exposure(self):
        policy = RiskPolicy(max_position_size=100.0, max_portfolio_exposure=1000.0)
        assert policy.validate(quantity=50.0, current_exposure=980.0) is False


# ---------------------------------------------------------------------------
# PaperBroker (integration of components)
# ---------------------------------------------------------------------------


class TestPaperBroker:
    """The paper broker orchestrates execution, fees, slippage, and risk
    to produce a FillResult for a simulated order."""

    def _default_broker(self) -> PaperBroker:
        return PaperBroker(
            execution_model=BidAskExecution(),
            slippage_model=SlippageModel(slippage_bps=50.0),
            fee_model=FeeModel(fee_rate=0.02),
            risk_policy=RiskPolicy(
                max_position_size=100.0,
                max_portfolio_exposure=10000.0,
            ),
        )

    def test_buy_fill(self):
        broker = self._default_broker()
        result = broker.execute(
            side=OrderSide.BUY,
            quantity=10.0,
            best_bid=0.55,
            best_ask=0.60,
            current_exposure=0.0,
        )
        assert result is not None
        # Base price = 0.60 (ask), slippage = 0.60 * 50/10000 = 0.003
        # Fill price = 0.603
        assert result.fill_price == pytest.approx(0.603)
        assert result.fill_quantity == pytest.approx(10.0)
        # Fee = 10 * 0.603 * 0.02 = 0.1206
        assert float(result.fee_amount) == pytest.approx(0.1206, abs=0.001)
        assert float(result.slippage_amount) == pytest.approx(0.003, abs=0.001)

    def test_sell_fill(self):
        broker = self._default_broker()
        result = broker.execute(
            side=OrderSide.SELL,
            quantity=10.0,
            best_bid=0.55,
            best_ask=0.60,
            current_exposure=100.0,
        )
        assert result is not None
        # Base price = 0.55 (bid), slippage = 0.55 * 50/10000 = 0.00275
        # Fill price = 0.55 - 0.00275 = 0.54725
        assert result.fill_price == pytest.approx(0.54725)

    def test_risk_rejection(self):
        broker = self._default_broker()
        result = broker.execute(
            side=OrderSide.BUY,
            quantity=200.0,  # exceeds max_position_size=100
            best_bid=0.55,
            best_ask=0.60,
            current_exposure=0.0,
        )
        assert result is None

    def test_fill_has_explanation(self):
        broker = self._default_broker()
        result = broker.execute(
            side=OrderSide.BUY,
            quantity=10.0,
            best_bid=0.55,
            best_ask=0.60,
            current_exposure=0.0,
        )
        assert result is not None
        assert "ask" in result.explanation.lower() or "0.60" in result.explanation

    def test_zero_slippage_broker(self):
        broker = PaperBroker(
            execution_model=MidPriceExecution(),
            slippage_model=SlippageModel(slippage_bps=0.0),
            fee_model=FeeModel(fee_rate=0.0),
            risk_policy=RiskPolicy(max_position_size=1000.0, max_portfolio_exposure=100000.0),
        )
        result = broker.execute(
            side=OrderSide.BUY,
            quantity=10.0,
            best_bid=0.55,
            best_ask=0.60,
            current_exposure=0.0,
        )
        assert result is not None
        assert result.fill_price == pytest.approx(0.575)
        assert result.fee_amount == Decimal("0")
        assert result.slippage_amount == Decimal("0")
