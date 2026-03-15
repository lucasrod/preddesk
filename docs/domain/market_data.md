# Market Data Context

## Purpose

The Market Data bounded context is responsible for ingesting, normalizing, and persisting data from external prediction market venues. It forms the foundation of the system — all downstream analysis depends on accurate, timely market data.

## Key Entities

- **Event** — The real-world occurrence being predicted (e.g., "Will it rain tomorrow?"). Has a lifecycle: `OPEN → CLOSED → RESOLVED`.
- **Market** — A tradable instrument linked to an Event. Characterized by type (BINARY), venue, and status.
- **PriceSnapshot** — A point-in-time observation of market state: best bid, best ask, mid-price, volume. Snapshots are append-only and never modified.

## Invariants

1. Every Market belongs to exactly one Event.
2. PriceSnapshots are immutable once created.
3. `mid_price = (best_bid + best_ask) / 2` is computed, not stored.
4. `spread = best_ask - best_bid` is always non-negative when both prices exist.
5. Timestamps are always UTC.

## Data Flow

```
External API → Ingestion Adapter → IngestMarkets Use Case → Event + Market + PriceSnapshot
```

The `IngestMarkets` use case:
1. Calls `ExternalMarketDataProvider.fetch_active_markets()`.
2. For each raw market: upserts Event, upserts Market, creates PriceSnapshot.
3. Returns an `IngestResult` summary (markets ingested, snapshots saved, errors).

## Design Decisions

- **Source IDs preserved**: Both `source_event_id` and `source_market_id` are stored to maintain traceability back to the external venue.
- **Idempotent upsert**: If a market already exists (matched by `source_market_id`), only a new snapshot is created. No duplicate markets.
- **Raw payload storage** (Sprint 2): Raw API responses will be persisted separately for audit and replay purposes.

## Code Reference

- Entities: `src/preddesk/domain/entities.py` → `Event`, `Market`, `PriceSnapshot`
- Ports: `src/preddesk/domain/ports.py` → `EventRepository`, `MarketRepository`, `PriceSnapshotRepository`, `ExternalMarketDataProvider`
- Use case: `src/preddesk/application/use_cases.py` → `IngestMarkets`
