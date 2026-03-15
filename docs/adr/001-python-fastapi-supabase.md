# ADR-001: Python + FastAPI + Supabase Postgres

## Status
Accepted

## Context
We need a backend stack for a prediction markets research workbench that supports rapid prototyping, scientific computing, strong typing, and easy testability.

## Decision
- **Python 3.13** — rich scientific/financial ecosystem, strong typing via Pydantic and mypy.
- **FastAPI** — async-ready, auto-generated OpenAPI docs, Pydantic-native.
- **Supabase (Postgres)** — managed Postgres with built-in auth, storage, and realtime. Eliminates operational overhead for a solo-developer MVP.
- **SQLAlchemy 2.0** — ORM layer between domain and Supabase Postgres.

## Consequences
- All domain logic is pure Python with no Supabase dependency.
- Supabase access is behind ports (repository interfaces), making it replaceable.
- `uv` manages the Python environment and dependencies.
