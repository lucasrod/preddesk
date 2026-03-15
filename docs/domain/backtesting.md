# Backtesting Context

## Purpose

The Backtesting bounded context replays historical price snapshots through a strategy and paper broker to evaluate performance. It is the primary tool for answering: "Would this strategy have worked on past data?"

## Key Components

- **Backtester** — The replay engine that sorts snapshots chronologically and feeds them to a strategy.
- **Strategy** (Protocol) — Any object with `on_snapshot(snapshot, position_qty) → (side, qty) | None`.
- **BacktestConfig** — Serializable configuration (strategy name, version, parameters).
- **BacktestMetrics** — Computed performance statistics.
- **BacktestResult** — Full output: config, fills, trade count, and metrics.
- **StrategyRun** — Persisted entity recording the backtest execution and its results.

## Critical Requirements

### 1. No Lookahead Bias

At time $t$, only data from $t$ and earlier is visible to the strategy. The backtester enforces this by:
- Sorting all snapshots by `captured_at` before replay.
- Feeding snapshots one at a time in chronological order.
- Never exposing future snapshots to the `on_snapshot` callback.

**Timeline visualization:**
```
t=0     t=1     t=2     t=3     t=4
 |-------|-------|-------|-------|
 S0      S1      S2      S3      S4
 ^
 Strategy sees only S0
         ^
         Strategy sees S0, S1
                 ^
                 Strategy sees S0..S2
```

### 2. Determinism

Same inputs (snapshots, strategy, config, broker) always produce the same output. The backtester has no random state and no external dependencies.

### 3. Reproducibility

Every backtest run is recorded as a `StrategyRun` entity with full config and summary metrics, enabling future comparison.

## Metrics (Spec Section 14.2)

| Metric | Description | Implemented |
|--------|-------------|-------------|
| `total_return` | Sum of realized PnL across all round-trips | Yes |
| `hit_rate` | Fraction of profitable round-trips | Yes |
| `max_drawdown` | Largest peak-to-trough decline in cumulative PnL | Yes |
| `avg_edge_captured` | Mean PnL per round-trip | Yes |
| `avg_holding_time_seconds` | Mean time between entry and exit | Yes |
| `turnover` | Total quantity traded across all fills | Yes |

## Methodology Risks

The spec (Section 14.3) requires explicit awareness of these pitfalls:

1. **Selection bias** — Only testing strategies that "look good" on the data you've seen.
2. **Survivorship bias** — Markets that resolved or were delisted may be missing from historical data.
3. **Lookahead bias** — Using future information in decisions. Prevented by the engine's chronological replay.
4. **Data snooping** — Tuning parameters on the same data used for evaluation. Mitigated by separating calibration and evaluation periods (user responsibility).
5. **Overfitting thresholds** — Optimizing signal thresholds to fit historical noise rather than real edge.

## Execution Flow

```
ExecuteBacktest UC → load snapshots → Backtester.run() → Strategy.on_snapshot() loop → PaperBroker.execute() → BacktestResult → persist StrategyRun
```

## Code Reference

- Domain engine: `src/preddesk/domain/backtester.py`
- Application use case: `src/preddesk/application/use_cases.py` → `ExecuteBacktest`
- Tests: `tests/unit/domain/test_backtester.py`, `tests/unit/application/test_execute_backtest.py`
- E2E: `tests/e2e/test_backtest_flow.py`
