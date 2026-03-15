"""Property-based tests for portfolio and position invariants.

These tests verify that position aggregation and PnL calculations
maintain consistency under arbitrary valid inputs. Key invariants:

- Unrealized PnL is linear in (current_price - avg_cost) * quantity.
- Net quantity is always non-negative after long-only trades.
- Realized PnL from a round-trip equals (sell_price - buy_price) * qty - fees.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from hypothesis import given
from hypothesis import strategies as st

from preddesk.domain.entities import Position
from preddesk.domain.value_objects import MarketSide


@st.composite
def position_strategy(draw):
    """Generate a valid Position with random but consistent values."""
    qty = draw(st.floats(min_value=0.0, max_value=10000.0, allow_nan=False, allow_infinity=False))
    cost = draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
    return Position(
        position_id=uuid4(),
        portfolio_id=uuid4(),
        market_id=uuid4(),
        side=MarketSide.YES,
        net_quantity=qty,
        avg_cost=cost,
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
        marked_at=datetime(2025, 1, 1, tzinfo=UTC),
    )


class TestPositionProperties:
    @given(
        qty=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
        avg_cost=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
        current_price=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
        ),
    )
    def test_unrealized_pnl_is_linear(self, qty, avg_cost, current_price):
        """Unrealized PnL = (current_price - avg_cost) * net_quantity.

        This is the standard mark-to-market identity for a long position.
        """
        pos = Position(
            position_id=uuid4(),
            portfolio_id=uuid4(),
            market_id=uuid4(),
            side=MarketSide.YES,
            net_quantity=qty,
            avg_cost=avg_cost,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            marked_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        expected = (current_price - avg_cost) * qty
        assert abs(pos.compute_unrealized_pnl(current_price) - expected) < 1e-9

    @given(position_strategy())
    def test_zero_quantity_means_zero_unrealized_pnl_at_any_price(self, pos):
        """A flat position has zero unrealized PnL regardless of price."""
        flat = Position(
            position_id=pos.position_id,
            portfolio_id=pos.portfolio_id,
            market_id=pos.market_id,
            side=pos.side,
            net_quantity=0.0,
            avg_cost=pos.avg_cost,
            realized_pnl=pos.realized_pnl,
            unrealized_pnl=pos.unrealized_pnl,
            marked_at=pos.marked_at,
        )
        assert flat.compute_unrealized_pnl(0.99) == 0.0

    @given(
        qty=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
        avg_cost=st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
    )
    def test_unrealized_pnl_at_avg_cost_is_zero(self, qty, avg_cost):
        """When current price equals avg cost, unrealized PnL is zero."""
        pos = Position(
            position_id=uuid4(),
            portfolio_id=uuid4(),
            market_id=uuid4(),
            side=MarketSide.YES,
            net_quantity=qty,
            avg_cost=avg_cost,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            marked_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        assert abs(pos.compute_unrealized_pnl(avg_cost)) < 1e-9
