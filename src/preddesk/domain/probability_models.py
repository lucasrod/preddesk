"""Probability estimation models for PredDesk.

Each model produces a probability estimate and optionally a confidence
interval. Models are designed to be simple, testable, and composable.

Model hierarchy:
- BaseRateModel: frequency-based (historical).
- BayesianUpdater: sequential Bayesian updating with explicit evidence.
- AnalystOverride: human-registered subjective estimate with explanation.

See docs/math/ for derivations and economic interpretation.
"""

from __future__ import annotations

import math

from preddesk.domain.value_objects import ConfidenceInterval


class ImpliedProbabilityModel:
    """Use market price directly as probability estimate.

    This is the simplest model and the baseline against which all others
    are compared. The implied probability is:

        p = price / overround

    With overround=1.0 (no vig), the price is the implied probability.
    With overround>1.0, the raw price overstates the true probability
    because the book has a margin built into the prices.
    """

    model_name: str = "implied_probability"

    def __init__(self, market_price: float, overround: float = 1.0) -> None:
        if market_price < 0.0:
            msg = f"market_price must be >= 0, got {market_price}"
            raise ValueError(msg)
        if market_price > overround:
            msg = f"market_price ({market_price}) cannot exceed overround ({overround})"
            raise ValueError(msg)
        self._price = market_price
        self._overround = overround

    def estimate(self) -> float:
        """Point estimate: price / overround."""
        if self._overround == 0.0:
            return 0.0
        return self._price / self._overround

    def confidence_interval(self) -> None:
        """No uncertainty model — implied probability is a point estimate."""
        return None


class BaseRateModel:
    """Estimate probability from historical frequencies.

    With optional Laplace smoothing:
        p = (successes + alpha) / (total + 2alpha)

    Confidence intervals use the Wilson score interval, which performs
    well even for small samples and extreme proportions.
    """

    model_name: str = "base_rate"

    def __init__(self, successes: int, total: int, smoothing: float = 0.0) -> None:
        if total <= 0:
            msg = f"total must be > 0, got {total}"
            raise ValueError(msg)
        if successes < 0:
            msg = f"successes must be >= 0, got {successes}"
            raise ValueError(msg)
        if successes > total:
            msg = f"successes ({successes}) cannot exceed total ({total})"
            raise ValueError(msg)
        self._successes = successes
        self._total = total
        self._smoothing = smoothing

    def estimate(self) -> float:
        """Point estimate of probability."""
        return (self._successes + self._smoothing) / (self._total + 2 * self._smoothing)

    def confidence_interval(self, z: float = 1.96) -> ConfidenceInterval:
        """Wilson score interval at the given z-level (default 95%).

        Wilson interval:
            center = (p̂ + z²/2n) / (1 + z²/n)
            margin = z * √(p̂(1-p̂)/n + z²/4n²) / (1 + z²/n)
            CI = [center - margin, center + margin]

        This interval has better coverage properties than the Wald interval
        for small samples and proportions near 0 or 1.
        """
        n = self._total
        p_hat = self._successes / n
        z2 = z * z

        denom = 1.0 + z2 / n
        center = (p_hat + z2 / (2 * n)) / denom
        margin = (z / denom) * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n))

        lower = max(0.0, center - margin)
        upper = min(1.0, center + margin)
        return ConfidenceInterval(lower=lower, upper=upper)


class BayesianUpdater:
    """Sequential Bayesian updater for binary hypotheses.

    Applies Bayes' theorem:
        P(H|E) = P(E|H) * P(H) / P(E)

    where P(E) = P(E|H)*P(H) + P(E|¬H)*P(¬H).

    The updater maintains state: each update's posterior becomes the
    next update's prior. The full history is tracked for auditability.
    """

    model_name: str = "bayesian_updater"

    def __init__(self, prior: float) -> None:
        if prior < 0.0 or prior > 1.0:
            msg = f"Prior must be in [0, 1], got {prior}"
            raise ValueError(msg)
        self._current = prior
        self._history: list[float] = [prior]

    @property
    def current(self) -> float:
        """Current posterior (or prior if no updates yet)."""
        return self._current

    @property
    def history(self) -> list[float]:
        """Full sequence: [prior, posterior_1, posterior_2, ...]."""
        return list(self._history)

    def update(self, likelihood_given_h: float, likelihood_given_not_h: float) -> float:
        """Update with new evidence and return the posterior.

        Args:
            likelihood_given_h: P(E|H) — probability of observing this
                evidence if the hypothesis is true.
            likelihood_given_not_h: P(E|¬H) — probability of observing
                this evidence if the hypothesis is false.

        Returns:
            The updated posterior probability.
        """
        if likelihood_given_h < 0.0 or likelihood_given_h > 1.0:
            msg = f"likelihood_given_h must be in [0, 1], got {likelihood_given_h}"
            raise ValueError(msg)
        if likelihood_given_not_h < 0.0 or likelihood_given_not_h > 1.0:
            msg = f"likelihood_given_not_h must be in [0, 1], got {likelihood_given_not_h}"
            raise ValueError(msg)

        prior = self._current
        p_evidence = likelihood_given_h * prior + likelihood_given_not_h * (1.0 - prior)

        # Degenerate case: if evidence is impossible under both hypotheses, keep prior.
        posterior = prior if p_evidence == 0.0 else (likelihood_given_h * prior) / p_evidence

        self._current = posterior
        self._history.append(posterior)
        return posterior


class AnalystOverride:
    """Human-registered subjective probability with mandatory explanation.

    This model exists because in research, hypotheses often precede
    automated estimation. Requiring an explanation ensures traceability.
    """

    model_name: str = "analyst_override"

    def __init__(
        self,
        probability: float,
        explanation: str,
        lower_bound: float | None = None,
        upper_bound: float | None = None,
    ) -> None:
        if probability < 0.0 or probability > 1.0:
            msg = f"probability must be in [0, 1], got {probability}"
            raise ValueError(msg)
        if not explanation.strip():
            msg = "explanation must be non-empty"
            raise ValueError(msg)
        self._probability = probability
        self._explanation = explanation
        self._lower_bound = lower_bound
        self._upper_bound = upper_bound

    def estimate(self) -> float:
        return self._probability

    @property
    def explanation(self) -> str:
        return self._explanation

    def confidence_interval(self) -> ConfidenceInterval | None:
        """Returns CI only if the analyst provided bounds."""
        if self._lower_bound is not None and self._upper_bound is not None:
            return ConfidenceInterval(lower=self._lower_bound, upper=self._upper_bound)
        return None
