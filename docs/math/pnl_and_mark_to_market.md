# PnL and Mark-to-Market

## Overview

PredDesk tracks profit and loss (PnL) at two levels: **realized PnL** (from closed trades) and **unrealized PnL** (from open positions marked to current prices). Understanding the distinction is critical for honest performance reporting.

## Realized PnL

When a position is closed (sell after buy), realized PnL for the round-trip is:

$$
\text{Realized PnL} = (P_{\text{sell}} - P_{\text{buy}}) \times Q - \text{fees}
$$

Where:
- $P_{\text{sell}}$ — fill price of the sell order
- $P_{\text{buy}}$ — average cost basis of the position
- $Q$ — quantity sold
- fees — total transaction costs (broker fees + slippage costs)

Realized PnL is **final** — it cannot change after the trade is completed.

## Unrealized PnL (Mark-to-Market)

For open positions, unrealized PnL is computed by marking the position to current market price:

$$
\text{Unrealized PnL} = (P_{\text{current}} - P_{\text{avg\_cost}}) \times Q_{\text{net}}
$$

Where:
- $P_{\text{current}}$ — latest observable price (typically mid-price)
- $P_{\text{avg\_cost}}$ — weighted average entry price
- $Q_{\text{net}}$ — current position quantity

Unrealized PnL fluctuates with every price update and is **not guaranteed**.

## Average Cost Basis

When adding to an existing position, the average cost is updated:

$$
\text{avg\_cost}_{\text{new}} = \frac{\text{avg\_cost}_{\text{old}} \times Q_{\text{old}} + P_{\text{fill}} \times Q_{\text{new}}}{Q_{\text{old}} + Q_{\text{new}}}
$$

## Binary Market Specifics

In binary prediction markets where contracts pay 1 if YES and 0 if NO:
- A **long YES** position at cost $c$ profits $(1 - c)$ per unit if the event resolves YES
- A **long YES** position at cost $c$ loses $c$ per unit if the event resolves NO
- Pre-resolution, unrealized PnL is marked to the current market mid-price

## Implementation Notes

- `Position.compute_unrealized_pnl(current_price)` implements the mark-to-market formula.
- The `Backtester` tracks realized PnL only (round-trip basis) — unrealized PnL at backtest end is not included in `total_return`.
- Fees are subtracted from realized PnL at the point of sell, using the `FeeModel` amount from the fill.
- All monetary amounts in PnL use Python floats for position tracking and `Decimal` for persisted PnL fields to avoid rounding drift in accounting.

## Pitfalls

- **Mark-to-market is not profit.** An unrealized gain can evaporate. The system displays both realized and unrealized PnL separately.
- **Average cost can mask losses.** Adding to a losing position lowers the average cost but does not eliminate the loss on earlier units.
- **Fees are real.** Paper trading with zero fees overstates performance. The system defaults to configurable fee and slippage models.

## Code Reference

- Position entity: `src/preddesk/domain/entities.py` → `Position`
- Paper broker fills: `src/preddesk/domain/paper_broker.py` → `FillResult`
- Backtester PnL tracking: `src/preddesk/domain/backtester.py` → `Backtester.run()`
