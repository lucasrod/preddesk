# Kelly Criterion

## Concept

The Kelly criterion determines the optimal bet size to maximize the expected logarithmic growth rate of capital. For a binary bet with win probability $p$ and net odds $b$ (payout per unit staked minus 1):

$$
f^* = \frac{p \cdot b - q}{b}
$$

where $q = 1 - p$.

## Why Fractional Kelly

Full Kelly is optimal only when:
- The probability estimate is perfectly calibrated.
- The bettor has an infinite time horizon.
- Utility is purely logarithmic.

In practice, probability estimates carry uncertainty. Full Kelly leads to large drawdowns when estimates are wrong. **Fractional Kelly** reduces variance at the cost of slower growth:

$$
f = \alpha \cdot f^*
$$

Common choices for $\alpha$:
- 0.25 (quarter Kelly) — conservative, our default.
- 0.50 (half Kelly) — moderate.
- 1.00 (full Kelly) — aggressive, not recommended.

## Position Size Cap

Even with fractional Kelly, extreme edge estimates can produce large bets. A `max_fraction` parameter caps the absolute position size.

## Implementation

`preddesk.domain.services.fractional_kelly(prob, odds, fraction=0.25, max_fraction=1.0)`

- Returns 0 when edge is non-positive (no bet).
- Default fraction is 0.25 — full Kelly is never the default.
- Result is clamped to `[0, max_fraction]`.

## Limitations

- Assumes independent bets (no correlation between market outcomes).
- Does not account for margin requirements or liquidity constraints.
- The odds parameter assumes a simple binary payout structure.
- Sensitive to estimation error in $p$ — small mis-calibrations can flip the sign of edge.
