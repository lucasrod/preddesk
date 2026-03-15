# ADR-004: Paper Broker Explainable Before Realistic

## Status
Accepted

## Context
A paper broker can range from trivially simple (fill at mid-price) to nearly production-grade (full order book simulation). The MVP should prioritize learning over fidelity.

## Decision
Start with a simple, explainable paper broker:
- Fill at best bid/ask + configurable slippage.
- Configurable fee model.
- Every fill includes an explanation of how price, fees, and slippage were computed.
- No partial fills in Phase 1.

## Consequences
- Users understand exactly how simulated PnL is computed.
- Results are reproducible and auditable.
- Sophistication (order book depth, partial fills) added in later phases.
