# ADR-003: No Live Trading in MVP

## Status
Accepted

## Context
Prediction markets involve real money. Bugs in execution logic can cause financial loss.

## Decision
Phase 1 (MVP) is research and paper trading only. No real orders are placed. The system simulates execution through a paper broker with configurable fees and slippage.

## Consequences
- Eliminates financial risk during development.
- Paper broker must be realistic enough to avoid misleading the user.
- Live trading will be introduced in Phase 3+ with approval flows and kill switches.
