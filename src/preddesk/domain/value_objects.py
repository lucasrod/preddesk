"""Domain value objects for PredDesk.

Value objects are immutable, identity-less, and validated at construction.
They form the atomic building blocks of the domain model — every probability,
price, and quantity in the system flows through these types.
"""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, field_validator, model_validator

from preddesk.domain.exceptions import (
    InvalidConfidenceIntervalError,
    InvalidPriceError,
    InvalidProbabilityError,
    InvalidQuantityError,
    InvalidTimeRangeError,
)


class Probability(BaseModel, frozen=True):
    """A probability value in [0, 1].

    This is the most fundamental type in a prediction-market system.
    Market prices, model estimates, and posteriors are all probabilities.
    """

    value: float

    @field_validator("value")
    @classmethod
    def _must_be_in_unit_interval(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            msg = f"Probability must be in [0, 1], got {v}"
            raise InvalidProbabilityError(msg)
        return v


class Price(BaseModel, frozen=True):
    """A non-negative price.

    In binary prediction markets, prices typically fall in [0, 1] where
    the price approximates the implied probability of the outcome.
    """

    value: float

    @field_validator("value")
    @classmethod
    def _must_be_non_negative(cls, v: float) -> float:
        if v < 0.0:
            msg = f"Price must be >= 0, got {v}"
            raise InvalidPriceError(msg)
        return v


class Money(BaseModel, frozen=True):
    """A monetary amount with explicit currency.

    Uses Decimal to avoid floating-point rounding errors in PnL tracking.
    """

    amount: Decimal
    currency: str = "USD"


class Quantity(BaseModel, frozen=True):
    """A non-negative, finite quantity of contracts.

    NaN and Inf are rejected because they would silently corrupt
    position and PnL calculations.
    """

    value: float

    @field_validator("value")
    @classmethod
    def _must_be_valid(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            msg = f"Quantity must be finite, got {v}"
            raise InvalidQuantityError(msg)
        if v < 0.0:
            msg = f"Quantity must be >= 0, got {v}"
            raise InvalidQuantityError(msg)
        return v


class Percentage(BaseModel, frozen=True):
    """A percentage value. Can be negative (losses) but must be finite."""

    value: float

    @field_validator("value")
    @classmethod
    def _must_be_finite(cls, v: float) -> float:
        if math.isnan(v) or math.isinf(v):
            msg = "Percentage must be finite"
            raise ValueError(msg)
        return v


class TimeRange(BaseModel, frozen=True):
    """A time interval where start <= end."""

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _start_not_after_end(self) -> TimeRange:
        if self.start > self.end:
            msg = f"TimeRange start ({self.start}) must be <= end ({self.end})"
            raise InvalidTimeRangeError(msg)
        return self


class ConfidenceInterval(BaseModel, frozen=True):
    """A confidence interval for probability estimates.

    Both bounds must be valid probabilities [0, 1] and lower <= upper.
    """

    lower: float
    upper: float

    @model_validator(mode="after")
    def _validate_bounds(self) -> ConfidenceInterval:
        if self.lower < 0.0 or self.lower > 1.0:
            msg = f"Lower bound must be in [0, 1], got {self.lower}"
            raise InvalidConfidenceIntervalError(msg)
        if self.upper < 0.0 or self.upper > 1.0:
            msg = f"Upper bound must be in [0, 1], got {self.upper}"
            raise InvalidConfidenceIntervalError(msg)
        if self.lower > self.upper:
            msg = f"Lower ({self.lower}) must be <= upper ({self.upper})"
            raise InvalidConfidenceIntervalError(msg)
        return self

    @property
    def width(self) -> float:
        """Width of the interval: upper - lower."""
        return self.upper - self.lower


class MarketProbabilitySpread(BaseModel, frozen=True):
    """Spread between model and market probability.

    Captures the perceived edge: if the model assigns a higher probability
    than the market price implies, there may be a buying opportunity.
    Edge is expressed in basis points (1 bps = 0.01%).
    """

    model_probability: float
    market_probability: float

    @field_validator("model_probability", "market_probability")
    @classmethod
    def _must_be_in_unit_interval(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            msg = f"Probability must be in [0, 1], got {v}"
            raise InvalidProbabilityError(msg)
        return v

    @property
    def edge_bps(self) -> float:
        """Edge in basis points: (model - market) * 10_000."""
        return (self.model_probability - self.market_probability) * 10_000

    @property
    def has_positive_edge(self) -> bool:
        """True if model probability exceeds market probability."""
        return self.model_probability > self.market_probability


class MarketSide(StrEnum):
    """Side of a binary market outcome."""

    YES = "YES"
    NO = "NO"


class OrderSide(StrEnum):
    """Direction of a trade order."""

    BUY = "BUY"
    SELL = "SELL"
