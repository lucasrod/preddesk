# ADR-005: TDD Mandatory for Domain and Application

## Status
Accepted

## Context
The system handles probabilistic calculations, financial simulations, and decision logic where subtle bugs can produce silently wrong results.

## Decision
- All domain and application code is developed test-first (Red → Green → Refactor).
- Target coverage: 95%+ for domain, 90%+ for application.
- Tests serve a dual purpose: verification and pedagogical documentation of financial/probabilistic concepts.
- Property-based tests (Hypothesis) for mathematical invariants.

## Consequences
- Slower initial velocity, much higher confidence in correctness.
- Tests become living documentation of domain rules and formulas.
- Refactoring is safe because invariants are encoded in tests.
