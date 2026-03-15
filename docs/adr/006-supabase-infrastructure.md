# ADR-006: Supabase as Infrastructure Layer

## Status
Accepted

## Context
The MVP needs persistence, authentication, file storage, and potentially realtime updates. Self-hosting Postgres plus building auth adds operational burden for a solo developer.

## Decision
Use Supabase as the infrastructure backend:
- **Postgres** — primary relational store (canonical + raw data).
- **Auth** — user management and API key handling.
- **Storage** — artifacts, exports, backtest results.
- **Realtime** — optional event streaming for live market updates.

All Supabase access goes through domain ports (repository protocols). The domain layer has zero knowledge of Supabase.

## Consequences
- Faster time to MVP: managed database, auth, and storage out of the box.
- Vendor coupling is limited to the infrastructure layer and can be swapped.
- SQLAlchemy 2.0 connects to Supabase Postgres as a standard Postgres database.
- Local development can use a local Postgres or Supabase CLI.
