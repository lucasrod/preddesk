# Expected Value

## Concept

For a binary contract that costs $c$ and pays $W$ if YES resolves:

$$
EV = p \cdot (W - c) - (1-p) \cdot c
$$

where $p$ is the model's estimated probability of YES.

When $W = 1$ (standard binary contract):

$$
EV = p - c
$$

## Interpretation

- **EV > 0**: the model believes the contract is underpriced — positive expected return.
- **EV = 0**: break-even under the model.
- **EV < 0**: the model believes the contract is overpriced.

## Break-Even Probability

The minimum $p$ for non-negative EV:

$$
p_{\text{be}} = \frac{c}{W}
$$

A rational trader buys only if $p_{\text{model}} > p_{\text{be}}$.

## Assumptions and Limitations

- Assumes no transaction costs beyond the initial cost $c$. When fees apply, the effective cost increases and the break-even probability shifts upward.
- Assumes the model probability is well-calibrated. Overconfident models will systematically overestimate EV.
- Does not account for the opportunity cost of capital or time value of money.

## Implementation

- `preddesk.domain.services.expected_value(model_prob, cost, payout=1.0)`
- `preddesk.domain.services.break_even_probability(cost, payout=1.0)`
