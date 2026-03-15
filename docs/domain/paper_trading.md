# Paper Trading Context

## Purpose

The Paper Trading bounded context simulates order execution without real money. It provides a realistic-enough trading environment for testing strategies, validating signals, and understanding transaction costs before risking capital.

## Key Entities

- **PaperOrder** — A simulated order (BUY/SELL) with quantity, limit price, and status (FILLED/REJECTED).
- **PaperFill** — The simulated execution: fill price, quantity, fees, and slippage.
- **Position** — Aggregated holding in a market: net quantity, average cost, realized and unrealized PnL.

## Paper Broker Architecture

The `PaperBroker` is composed of pluggable components following the Strategy pattern:

| Component | Purpose | Default |
|-----------|---------|---------|
| `ExecutionModel` | Determines fill price from order book | `BidAskExecution` (buy at ask, sell at bid) |
| `SlippageModel` | Adds realistic price impact | Configurable bps (default 50 bps) |
| `FeeModel` | Computes transaction fees | Configurable rate (default 2%) |
| `RiskPolicy` | Validates position limits | Max position size + max portfolio exposure |

## Execution Flow

```
Signal/Intent → SimulateOrder UC → RiskPolicy.validate() → ExecutionModel → SlippageModel → FeeModel → PaperOrder + PaperFill + Position
```

1. **Risk check**: `RiskPolicy` rejects orders that would exceed position or exposure limits.
2. **Price determination**: `ExecutionModel` selects base price from bid/ask.
3. **Slippage**: `SlippageModel` adjusts price adversely (buys get worse, sells get worse).
4. **Fees**: `FeeModel` computes fee amount based on fill notional.
5. **Position update**: Average cost is recalculated; realized PnL is tracked on sells.

## Invariants

1. A REJECTED order creates no fill and no position change.
2. Fees and slippage always make the fill price worse than the raw market price.
3. Position `net_quantity` is non-negative (no short selling in Phase 1).
4. Average cost is a weighted average of all entry prices.

## Design Decisions

- **Explainability first**: Every `FillResult` includes an explanation string describing how the fill price was computed. This makes the paper broker a teaching tool, not a black box.
- **No partial fills in Phase 1**: Orders are fully filled or fully rejected. Partial fills add complexity without proportional learning value in the MVP.
- **Kelly capped by default**: `PositionSizer.kelly()` uses fractional Kelly (default 25%) because full Kelly is theoretically optimal but practically dangerous with estimated probabilities.

## Code Reference

- Paper broker: `src/preddesk/domain/paper_broker.py`
- Use case: `src/preddesk/application/use_cases.py` → `SimulateOrder`
- Tests: `tests/unit/domain/test_paper_broker.py`, `tests/unit/application/test_simulate_order.py`
- Math: `docs/math/kelly.md`, `docs/math/pnl_and_mark_to_market.md`
