# Implied Probability

## Concept

In a binary prediction market, a contract pays $1 if the event resolves YES and $0 otherwise. The market price of a YES contract directly implies the market's consensus probability:

$$
p_{\text{implied}} = \text{price}_{\text{YES}}
$$

For the NO side: $p_{\text{NO}} = 1 - \text{price}_{\text{YES}}$.

## Overround (Vig)

In practice, the sum of YES and NO prices often exceeds 1.0 — this is the **overround** or **vig**, which represents the market maker's edge:

$$
\text{overround} = \text{price}_{\text{YES}} + \text{price}_{\text{NO}}
$$

To recover true implied probabilities, normalize by the overround:

$$
p_{\text{normalized}} = \frac{\text{price}}{\text{overround}}
$$

## Implementation

`preddesk.domain.services.implied_probability(price, overround=1.0)`

- `price` must be in [0, 1].
- `overround` defaults to 1.0 (no vig). When > 1, the function normalizes.

## Limitations

- Assumes the market is efficient enough for prices to approximate probabilities.
- Does not account for liquidity risk: thin markets may have prices that reflect limited participation rather than true consensus.
- Overround normalization assumes the vig is distributed proportionally, which is a simplification.
