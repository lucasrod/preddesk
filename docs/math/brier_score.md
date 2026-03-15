# Brier Score

## Overview

The Brier score measures the accuracy of probabilistic predictions for binary events. It is the primary calibration metric in PredDesk for evaluating how well model probabilities correspond to observed outcomes.

## Formula

For $N$ binary predictions:

$$
BS = \frac{1}{N} \sum_{i=1}^{N} (f_i - o_i)^2
$$

Where:
- $f_i$ — forecasted probability for event $i$
- $o_i$ — observed outcome (1 if the event occurred, 0 otherwise)

## Interpretation

| Score | Meaning |
|-------|---------|
| 0.0 | Perfect prediction — every forecast matched the outcome exactly |
| 0.25 | Equivalent to always predicting 0.50 (maximum ignorance for balanced events) |
| 1.0 | Worst possible — every prediction was maximally wrong |

**Lower is better.** The Brier score penalizes confident wrong predictions more heavily than uncertain ones, which makes it a proper scoring rule.

## Properties

- **Proper scoring rule**: A forecaster maximizes expected score by reporting true beliefs. There is no incentive to misreport probabilities.
- **Decomposition**: The Brier score can be decomposed into calibration, resolution, and uncertainty components (not currently implemented).
- **Sensitivity to base rate**: In rare-event markets, even a naive "always predict the base rate" model can achieve low Brier scores, so it should be compared against a baseline.

## Numerical Examples

1. **Perfect**: forecast 1.0, outcome 1 → $(1.0 - 1)^2 = 0.0$
2. **Totally wrong**: forecast 1.0, outcome 0 → $(1.0 - 0)^2 = 1.0$
3. **Uncertain**: forecast 0.5, outcome 1 → $(0.5 - 1)^2 = 0.25$

## Implementation Notes

- The function validates that forecasts are in $[0, 1]$ and outcomes are in $\{0, 1\}$.
- Empty input raises `ValueError`.
- The Brier score is available as a standalone function in `services.py` and can be integrated into backtest metrics for post-hoc calibration assessment.

## Code Reference

- Implementation: `src/preddesk/domain/services.py` → `brier_score()`
- Tests: `tests/unit/domain/test_services.py` → `TestBrierScore`
