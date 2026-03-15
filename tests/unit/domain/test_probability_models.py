"""Unit tests for probability models.

The probability engine provides multiple estimation models, each with
different assumptions and use cases. Tests verify both correctness
and document the mathematical foundations.

Models tested:
- BaseRateModel: frequency-based estimation from historical data.
- BayesianUpdater: updates a prior with new evidence via Bayes' theorem.
- AnalystOverride: human-in-the-loop probability with explanation.
"""

import pytest

from preddesk.domain.probability_models import (
    AnalystOverride,
    BaseRateModel,
    BayesianUpdater,
    ImpliedProbabilityModel,
)

# ---------------------------------------------------------------------------
# BaseRateModel
# ---------------------------------------------------------------------------


class TestBaseRateModel:
    """The base-rate model estimates probability from historical frequencies.

    If 7 out of 10 similar events resolved YES, the base rate is 0.70.
    This is the simplest credible model and serves as a benchmark.

    The model also supports a Laplace smoothing parameter (pseudocounts)
    to avoid 0/1 extremes with small samples:

        p = (successes + alpha) / (total + 2alpha)

    where alpha is the smoothing parameter (default 0, no smoothing).
    """

    def test_basic_rate(self):
        model = BaseRateModel(successes=7, total=10)
        assert model.estimate() == pytest.approx(0.70)

    def test_all_successes(self):
        model = BaseRateModel(successes=10, total=10)
        assert model.estimate() == pytest.approx(1.0)

    def test_no_successes(self):
        model = BaseRateModel(successes=0, total=10)
        assert model.estimate() == pytest.approx(0.0)

    def test_laplace_smoothing(self):
        """With alpha=1 (Laplace): p = (7+1) / (10+2) = 8/12 ≈ 0.6667.
        Smoothing pulls extreme estimates toward 0.5."""
        model = BaseRateModel(successes=7, total=10, smoothing=1.0)
        assert model.estimate() == pytest.approx(8.0 / 12.0)

    def test_smoothing_prevents_zero(self):
        """With smoothing, 0 successes no longer yields exactly 0."""
        model = BaseRateModel(successes=0, total=10, smoothing=1.0)
        assert model.estimate() > 0.0

    def test_smoothing_prevents_one(self):
        """With smoothing, all successes no longer yields exactly 1."""
        model = BaseRateModel(successes=10, total=10, smoothing=1.0)
        assert model.estimate() < 1.0

    def test_rejects_negative_successes(self):
        with pytest.raises(ValueError):
            BaseRateModel(successes=-1, total=10)

    def test_rejects_successes_exceeding_total(self):
        with pytest.raises(ValueError):
            BaseRateModel(successes=11, total=10)

    def test_rejects_zero_total(self):
        with pytest.raises(ValueError):
            BaseRateModel(successes=0, total=0)

    def test_confidence_interval_widens_with_small_samples(self):
        """Fewer observations → wider interval (more uncertainty).
        Uses the Wilson score interval."""
        small = BaseRateModel(successes=3, total=5)
        large = BaseRateModel(successes=60, total=100)
        ci_small = small.confidence_interval()
        ci_large = large.confidence_interval()
        assert ci_small.width > ci_large.width

    def test_confidence_interval_contains_estimate(self):
        model = BaseRateModel(successes=7, total=10)
        ci = model.confidence_interval()
        est = model.estimate()
        assert ci.lower <= est <= ci.upper

    def test_model_name(self):
        model = BaseRateModel(successes=7, total=10)
        assert model.model_name == "base_rate"


# ---------------------------------------------------------------------------
# BayesianUpdater
# ---------------------------------------------------------------------------


class TestBayesianUpdater:
    """Bayesian updating computes the posterior probability given prior
    beliefs and new evidence:

        P(H|E) = P(E|H) * P(H) / P(E)

    where:
    - P(H) = prior probability of the hypothesis
    - P(E|H) = likelihood of evidence given hypothesis is true
    - P(E|¬H) = likelihood of evidence given hypothesis is false
    - P(E) = P(E|H)*P(H) + P(E|¬H)*P(¬H) — total probability of evidence

    The updater supports sequential updates: each posterior becomes
    the prior for the next piece of evidence.
    """

    def test_evidence_increases_probability(self):
        """Strong evidence for H should increase posterior above prior.

        Prior: 0.50, Likelihood: P(E|H)=0.90, P(E|¬H)=0.20
        P(E) = 0.90*0.50 + 0.20*0.50 = 0.55
        Posterior = 0.90*0.50 / 0.55 ≈ 0.8182
        """
        updater = BayesianUpdater(prior=0.50)
        posterior = updater.update(likelihood_given_h=0.90, likelihood_given_not_h=0.20)
        assert posterior == pytest.approx(0.9 * 0.5 / 0.55, rel=1e-4)
        assert posterior > 0.50

    def test_evidence_decreases_probability(self):
        """Evidence against H should decrease posterior below prior.

        Prior: 0.50, P(E|H)=0.10, P(E|¬H)=0.80
        P(E) = 0.10*0.50 + 0.80*0.50 = 0.45
        Posterior = 0.10*0.50 / 0.45 ≈ 0.1111
        """
        updater = BayesianUpdater(prior=0.50)
        posterior = updater.update(likelihood_given_h=0.10, likelihood_given_not_h=0.80)
        assert posterior < 0.50

    def test_neutral_evidence_preserves_prior(self):
        """When P(E|H) == P(E|¬H), evidence is uninformative.
        Posterior should equal prior."""
        updater = BayesianUpdater(prior=0.60)
        posterior = updater.update(likelihood_given_h=0.50, likelihood_given_not_h=0.50)
        assert posterior == pytest.approx(0.60)

    def test_sequential_updates(self):
        """Multiple updates: each posterior feeds into the next.

        Start at 0.50, two confirmatory pieces of evidence.
        Posterior should monotonically increase.
        """
        updater = BayesianUpdater(prior=0.50)
        p1 = updater.update(likelihood_given_h=0.80, likelihood_given_not_h=0.30)
        p2 = updater.update(likelihood_given_h=0.80, likelihood_given_not_h=0.30)
        assert p1 > 0.50
        assert p2 > p1

    def test_current_returns_latest(self):
        updater = BayesianUpdater(prior=0.50)
        assert updater.current == pytest.approx(0.50)
        updater.update(likelihood_given_h=0.90, likelihood_given_not_h=0.10)
        assert updater.current > 0.50

    def test_history_tracks_all_posteriors(self):
        updater = BayesianUpdater(prior=0.50)
        updater.update(likelihood_given_h=0.90, likelihood_given_not_h=0.10)
        updater.update(likelihood_given_h=0.70, likelihood_given_not_h=0.40)
        assert len(updater.history) == 3  # prior + 2 updates

    def test_rejects_invalid_prior(self):
        with pytest.raises(ValueError):
            BayesianUpdater(prior=-0.1)
        with pytest.raises(ValueError):
            BayesianUpdater(prior=1.1)

    def test_rejects_invalid_likelihoods(self):
        updater = BayesianUpdater(prior=0.50)
        with pytest.raises(ValueError):
            updater.update(likelihood_given_h=-0.1, likelihood_given_not_h=0.5)
        with pytest.raises(ValueError):
            updater.update(likelihood_given_h=0.5, likelihood_given_not_h=1.1)

    def test_model_name(self):
        updater = BayesianUpdater(prior=0.50)
        assert updater.model_name == "bayesian_updater"


# ---------------------------------------------------------------------------
# AnalystOverride
# ---------------------------------------------------------------------------


class TestAnalystOverride:
    """Analyst override lets a human register a subjective probability
    with a mandatory explanation. This is useful when domain expertise
    precedes any automated model.

    The explanation is required because unexplained numbers are
    untraceable — a core anti-pattern in quantitative research.
    """

    def test_creation(self):
        ao = AnalystOverride(
            probability=0.75,
            explanation="Polling data strongly favors YES.",
        )
        assert ao.estimate() == pytest.approx(0.75)

    def test_requires_explanation(self):
        with pytest.raises(ValueError):
            AnalystOverride(probability=0.75, explanation="")

    def test_rejects_invalid_probability(self):
        with pytest.raises(ValueError):
            AnalystOverride(probability=1.5, explanation="test")

    def test_optional_confidence_interval(self):
        ao = AnalystOverride(
            probability=0.70,
            explanation="Moderate confidence.",
            lower_bound=0.55,
            upper_bound=0.85,
        )
        ci = ao.confidence_interval()
        assert ci is not None
        assert ci.lower == pytest.approx(0.55)
        assert ci.upper == pytest.approx(0.85)

    def test_no_confidence_interval_by_default(self):
        ao = AnalystOverride(
            probability=0.70,
            explanation="Just a guess.",
        )
        assert ao.confidence_interval() is None

    def test_model_name(self):
        ao = AnalystOverride(probability=0.5, explanation="coin flip")
        assert ao.model_name == "analyst_override"


# ---------------------------------------------------------------------------
# ImpliedProbabilityModel
# ---------------------------------------------------------------------------


class TestImpliedProbabilityModel:
    """The implied probability model uses the market price itself as the
    probability estimate. It is the simplest possible model and serves
    as the baseline/benchmark against which all other models are compared.

    Implied probability: p = price / overround

    With overround=1.0 (no vig), p = price directly.
    With overround>1.0, the raw price overstates the true probability.
    """

    def test_basic_estimate(self):
        """Price 0.65 with no overround → implied probability 0.65."""
        model = ImpliedProbabilityModel(market_price=0.65)
        assert model.estimate() == pytest.approx(0.65)

    def test_with_overround(self):
        """Price 0.65 with overround 1.10 → 0.65/1.10 ≈ 0.5909."""
        model = ImpliedProbabilityModel(market_price=0.65, overround=1.10)
        assert model.estimate() == pytest.approx(0.65 / 1.10, rel=1e-4)

    def test_boundary_zero(self):
        model = ImpliedProbabilityModel(market_price=0.0)
        assert model.estimate() == pytest.approx(0.0)

    def test_boundary_one(self):
        model = ImpliedProbabilityModel(market_price=1.0)
        assert model.estimate() == pytest.approx(1.0)

    def test_rejects_negative_price(self):
        with pytest.raises(ValueError):
            ImpliedProbabilityModel(market_price=-0.1)

    def test_rejects_price_above_overround(self):
        """Price cannot exceed overround (would yield p > 1)."""
        with pytest.raises(ValueError):
            ImpliedProbabilityModel(market_price=1.2, overround=1.0)

    def test_confidence_interval_is_none(self):
        """Implied probability has no uncertainty model — returns None."""
        model = ImpliedProbabilityModel(market_price=0.65)
        assert model.confidence_interval() is None

    def test_model_name(self):
        model = ImpliedProbabilityModel(market_price=0.50)
        assert model.model_name == "implied_probability"
