# Bayesian Updating

## Overview

Bayesian updating is the principled method for revising probability estimates as new evidence arrives. In PredDesk, the `BayesianUpdater` model uses this to sequentially incorporate evidence into a market probability estimate.

## Formula

$$
P(H \mid E) = \frac{P(E \mid H) \cdot P(H)}{P(E)}
$$

Where:
- $P(H)$ — **prior**: our current probability estimate before seeing evidence
- $P(E \mid H)$ — **likelihood**: how likely the evidence is if the hypothesis is true
- $P(E)$ — **marginal likelihood**: total probability of observing the evidence
- $P(H \mid E)$ — **posterior**: updated probability after incorporating evidence

The marginal likelihood is computed via the law of total probability:

$$
P(E) = P(E \mid H) \cdot P(H) + P(E \mid \neg H) \cdot (1 - P(H))
$$

## Likelihood Ratio Form

An equivalent and sometimes more intuitive formulation uses the **likelihood ratio**:

$$
\text{LR} = \frac{P(E \mid H)}{P(E \mid \neg H)}
$$

When $\text{LR} > 1$, the evidence supports $H$ and the posterior increases.
When $\text{LR} < 1$, the evidence supports $\neg H$ and the posterior decreases.

## Implementation Notes

- **Sequential updates**: The `BayesianUpdater` applies updates one at a time. Each posterior becomes the next prior, so order of evidence does not matter (commutativity of Bayes' rule for independent evidence).
- **History tracking**: Every update is recorded with prior, likelihoods, and posterior for auditability.
- **Edge case**: If $P(E) = 0$, the update is skipped (degenerate evidence).
- **Laplace smoothing is not applied here** — that belongs to the `BaseRateModel`. The Bayesian updater expects calibrated likelihoods.

## Assumptions and Limitations

- Assumes conditional independence of evidence given hypothesis (naive Bayes assumption).
- Likelihoods must be provided by the user or a calibrated source — garbage in, garbage out.
- Does not handle continuous evidence distributions; only discrete likelihood values.

## Code Reference

- Implementation: `src/preddesk/domain/probability_models.py` → `BayesianUpdater`
- Tests: `tests/unit/domain/test_probability_models.py` → `TestBayesianUpdater`
