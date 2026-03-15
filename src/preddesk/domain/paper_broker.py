"""Paper broker for PredDesk.

Simulates trade execution with configurable components:
- ExecutionModel: determines the base fill price (mid-price or bid/ask).
- SlippageModel: applies adverse price movement.
- FeeModel: computes transaction fees.
- RiskPolicy: validates orders against position and portfolio limits.
- PositionSizer: determines order quantity.

The broker is deterministic and explainable — every fill includes a
breakdown of how the final price was computed.

See ADR-004 for design rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from preddesk.domain.value_objects import OrderSide

# ---------------------------------------------------------------------------
# Slippage
# ---------------------------------------------------------------------------


class SlippageModel:
    """Configurable slippage as basis points on the base price.

    BUY: slippage increases price (adverse for buyer).
    SELL: slippage decreases price (adverse for seller).
    """

    def __init__(self, slippage_bps: float = 0.0) -> None:
        self._slippage_bps = slippage_bps

    def apply(self, base_price: float, side: OrderSide) -> float:
        slip = base_price * self._slippage_bps / 10_000.0
        if side == OrderSide.BUY:
            return base_price + slip
        return base_price - slip

    def slippage_amount(self, base_price: float) -> Decimal:
        return Decimal(str(base_price * self._slippage_bps / 10_000.0))


# ---------------------------------------------------------------------------
# Fees
# ---------------------------------------------------------------------------


class FeeModel:
    """Percentage-of-notional fee model.

    fee = quantity * fill_price * fee_rate
    """

    def __init__(self, fee_rate: float = 0.0) -> None:
        self._fee_rate = fee_rate

    def compute(self, quantity: float, fill_price: float) -> Decimal:
        return Decimal(str(round(quantity * fill_price * self._fee_rate, 10)))


# ---------------------------------------------------------------------------
# Execution models
# ---------------------------------------------------------------------------


class ExecutionModel(Protocol):
    def fill_price(self, side: OrderSide, best_bid: float, best_ask: float) -> float: ...


class MidPriceExecution:
    """Fill at mid-price: (bid + ask) / 2. Naive baseline."""

    def fill_price(self, side: OrderSide, best_bid: float, best_ask: float) -> float:
        return (best_bid + best_ask) / 2.0


class BidAskExecution:
    """BUY at ask, SELL at bid. Realistic-lite for Phase 1."""

    def fill_price(self, side: OrderSide, best_bid: float, best_ask: float) -> float:
        if side == OrderSide.BUY:
            return best_ask
        return best_bid


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------


class PositionSizer:
    """Determines order quantity based on sizing strategy."""

    def __init__(self, strategy: str, param: float) -> None:
        self._strategy = strategy
        self._param = param

    @classmethod
    def fixed(cls, units: float) -> PositionSizer:
        return cls(strategy="fixed", param=units)

    @classmethod
    def fixed_dollar(cls, risk_amount: float) -> PositionSizer:
        return cls(strategy="fixed_dollar", param=risk_amount)

    @classmethod
    def kelly(cls, kelly_fraction: float) -> PositionSizer:
        return cls(strategy="kelly", param=kelly_fraction)

    def compute(self, bankroll: float, price: float) -> float:
        if self._strategy == "fixed":
            return self._param
        elif self._strategy == "fixed_dollar":
            return self._param / price
        elif self._strategy == "kelly":
            return (self._param * bankroll) / price
        msg = f"Unknown sizing strategy: {self._strategy}"
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Risk policy
# ---------------------------------------------------------------------------


class RiskPolicy:
    """Validates orders against risk limits."""

    def __init__(self, max_position_size: float, max_portfolio_exposure: float) -> None:
        self._max_position_size = max_position_size
        self._max_portfolio_exposure = max_portfolio_exposure

    def validate(self, quantity: float, current_exposure: float) -> bool:
        if quantity > self._max_position_size:
            return False
        return not current_exposure + quantity > self._max_portfolio_exposure


# ---------------------------------------------------------------------------
# Fill result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FillResult:
    """Result of a simulated order execution."""

    fill_price: float
    fill_quantity: float
    fee_amount: Decimal
    slippage_amount: Decimal
    side: OrderSide
    explanation: str


# ---------------------------------------------------------------------------
# Paper broker
# ---------------------------------------------------------------------------


class PaperBroker:
    """Orchestrates simulated order execution.

    Composes execution model, slippage, fees, and risk policy to
    produce a FillResult. Returns None if the order is rejected by
    risk policy.
    """

    def __init__(
        self,
        execution_model: ExecutionModel,
        slippage_model: SlippageModel,
        fee_model: FeeModel,
        risk_policy: RiskPolicy,
    ) -> None:
        self._execution = execution_model
        self._slippage = slippage_model
        self._fees = fee_model
        self._risk = risk_policy

    def execute(
        self,
        side: OrderSide,
        quantity: float,
        best_bid: float,
        best_ask: float,
        current_exposure: float,
    ) -> FillResult | None:
        """Simulate an order and return the fill, or None if rejected."""
        if not self._risk.validate(quantity, current_exposure):
            return None

        base_price = self._execution.fill_price(side, best_bid, best_ask)
        fill_price = self._slippage.apply(base_price, side)
        slip_amount = self._slippage.slippage_amount(base_price)
        fee = self._fees.compute(quantity, fill_price)

        side_label = "ask" if side == OrderSide.BUY else "bid"
        explanation = (
            f"Filled {side.value} {quantity} @ {fill_price:.6f} "
            f"(base={base_price:.4f} from {side_label}, "
            f"slippage={float(slip_amount):.6f}, fee={float(fee):.6f})"
        )

        return FillResult(
            fill_price=fill_price,
            fill_quantity=quantity,
            fee_amount=fee,
            slippage_amount=slip_amount,
            side=side,
            explanation=explanation,
        )
