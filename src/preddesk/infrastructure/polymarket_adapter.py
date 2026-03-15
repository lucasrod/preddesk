"""Polymarket CLOB API adapter.

Implements the ExternalMarketDataProvider port for Polymarket's
REST API. Normalizes raw JSON payloads into the intermediate dict
format consumed by IngestMarkets.

The adapter uses httpx for HTTP calls and handles:
- Payload normalization (raw Polymarket JSON → canonical dict)
- Missing optional fields (graceful defaults)
- Forward compatibility (extra fields ignored)
"""

from __future__ import annotations

import httpx


def normalize_market_payload(raw: dict) -> dict:  # type: ignore[type-arg]
    """Map a raw Polymarket market JSON to the canonical intermediate format.

    This is the core contract: the raw provider payload is transformed into
    a dict with keys expected by IngestMarkets._process_one().

    Required fields:
        - condition_id: unique market identifier on Polymarket

    Optional fields get sensible defaults when absent.
    """
    condition_id = raw["condition_id"]  # Required — KeyError if missing

    # Extract YES token price as last_price if available
    tokens = raw.get("tokens", [])
    yes_price = None
    for tok in tokens:
        if tok.get("outcome", "").lower() == "yes":
            yes_price = tok.get("price")
            break

    return {
        "source_market_id": condition_id,
        "source_event_id": condition_id,  # Polymarket uses condition_id for both
        "event_title": raw.get("question", ""),
        "event_category": raw.get("category", ""),
        "venue": "polymarket",
        "market_type": "BINARY",
        "best_bid": raw.get("best_bid"),
        "best_ask": raw.get("best_ask"),
        "last_price": raw.get("last_trade_price", yes_price),
        "volume": raw.get("volume"),
    }


class PolymarketAdapter:
    """Adapter for the Polymarket CLOB REST API.

    Implements ExternalMarketDataProvider (structural subtyping via Protocol).
    """

    def __init__(self, base_url: str = "https://clob.polymarket.com") -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(base_url=self._base_url, timeout=30.0)

    def fetch_active_markets(self) -> list[dict]:  # type: ignore[type-arg]
        """Fetch all active markets and normalize each payload."""
        resp = self._client.get("/markets")
        resp.raise_for_status()
        raw_markets = resp.json()
        return [normalize_market_payload(m) for m in raw_markets]

    def fetch_market_detail(self, source_market_id: str) -> dict:  # type: ignore[type-arg]
        """Fetch a single market by condition_id and normalize."""
        resp = self._client.get(f"/markets/{source_market_id}")
        resp.raise_for_status()
        return normalize_market_payload(resp.json())

    def fetch_price_snapshot(self, source_market_id: str) -> dict:  # type: ignore[type-arg]
        """Fetch current price data for a market."""
        resp = self._client.get(f"/markets/{source_market_id}")
        resp.raise_for_status()
        raw = resp.json()
        return {
            "best_bid": raw.get("best_bid"),
            "best_ask": raw.get("best_ask"),
            "last_price": raw.get("last_trade_price"),
            "volume": raw.get("volume"),
        }
