"""Domain exceptions for PredDesk.

All domain-level errors inherit from DomainError to allow
callers to catch domain violations uniformly.

Validation exceptions also inherit from ValueError so that Pydantic
field_validators can raise them and Pydantic wraps them into
ValidationError as usual.
"""


class DomainError(Exception):
    """Base class for all domain errors."""


class InvalidProbabilityError(DomainError, ValueError):
    """Probability value outside [0, 1]."""


class InvalidPriceError(DomainError, ValueError):
    """Price value is negative or otherwise invalid."""


class InvalidQuantityError(DomainError, ValueError):
    """Quantity is negative, NaN, or infinite."""


class InvalidTimeRangeError(DomainError, ValueError):
    """TimeRange where start > end."""


class InvalidConfidenceIntervalError(DomainError, ValueError):
    """ConfidenceInterval where lower > upper or bounds outside [0, 1]."""


class InvalidOrderError(DomainError, ValueError):
    """Order violates business rules."""
