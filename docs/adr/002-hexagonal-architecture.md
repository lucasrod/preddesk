# ADR-002: Hexagonal Architecture

## Status
Accepted

## Context
The system must be testable in isolation, allow swapping data providers, and keep domain logic free from infrastructure concerns.

## Decision
Adopt Hexagonal (Ports and Adapters) architecture:
- **Domain** — entities, value objects, services, domain exceptions. Zero external dependencies.
- **Application** — use cases / orchestration. Depends only on domain ports.
- **Infrastructure** — adapters (Supabase repos, Polymarket client, HTTP). Implements ports.
- **Interface** — REST API, CLI, web frontend. Calls application layer.

## Consequences
- Domain can be fully tested with fakes/stubs.
- Adding a new data source means writing one adapter, no domain changes.
- Slightly more files/boilerplate than a flat architecture, justified by testability gains.
