"""Contract tests for the Polymarket adapter.

Contract tests verify that the adapter correctly maps external provider
payloads to the canonical domain model. They use realistic JSON shapes
captured from the Polymarket CLOB API and verify:

1. Happy path: full payload → canonical entities.
2. Missing optional fields → graceful defaults.
3. Schema changes / extra fields → no crash (forward-compatible).
4. Malformed data → explicit error handling.

These tests do NOT hit the network — they use static fixtures.
"""

from preddesk.infrastructure.polymarket_adapter import (
    PolymarketAdapter,
    normalize_market_payload,
)

# ---------------------------------------------------------------------------
# Realistic Polymarket CLOB payload fixtures
# ---------------------------------------------------------------------------

FULL_MARKET_PAYLOAD = {
    "condition_id": "0xabc123",
    "question": "Will Bitcoin exceed $100k by end of 2025?",
    "description": "This market resolves YES if BTC/USD exceeds $100,000.",
    "market_slug": "will-bitcoin-exceed-100k-2025",
    "end_date_iso": "2025-12-31T23:59:59Z",
    "game_start_time": "",
    "tokens": [
        {"token_id": "tok_yes", "outcome": "Yes", "price": 0.62, "winner": False},
        {"token_id": "tok_no", "outcome": "No", "price": 0.38, "winner": False},
    ],
    "active": True,
    "closed": False,
    "category": "crypto",
    "volume": 1500000.0,
    "liquidity": 250000.0,
    "best_bid": 0.60,
    "best_ask": 0.64,
    "last_trade_price": 0.62,
}

MINIMAL_PAYLOAD = {
    "condition_id": "0xdef456",
    "question": "Will it rain tomorrow?",
    "tokens": [
        {"token_id": "tok_yes", "outcome": "Yes", "price": 0.50},
    ],
    "active": True,
    "closed": False,
}

PAYLOAD_WITH_EXTRA_FIELDS = {
    **FULL_MARKET_PAYLOAD,
    "new_api_field": "unexpected",
    "another_new_field": {"nested": True},
}

MALFORMED_PAYLOAD_NO_CONDITION = {
    "question": "Missing condition_id",
    "tokens": [],
    "active": True,
    "closed": False,
}


# ---------------------------------------------------------------------------
# Contract tests: normalize_market_payload
# ---------------------------------------------------------------------------


class TestNormalizeMarketPayload:
    """Tests for the normalization function that maps raw Polymarket
    JSON to the intermediate dict consumed by IngestMarkets."""

    def test_full_payload_maps_all_fields(self):
        """All fields from a complete payload are extracted correctly."""
        result = normalize_market_payload(FULL_MARKET_PAYLOAD)

        assert result["source_market_id"] == "0xabc123"
        assert result["source_event_id"] == "0xabc123"
        assert result["event_title"] == "Will Bitcoin exceed $100k by end of 2025?"
        assert result["venue"] == "polymarket"
        assert result["market_type"] == "BINARY"
        assert result["event_category"] == "crypto"
        assert result["best_bid"] == 0.60
        assert result["best_ask"] == 0.64
        assert result["last_price"] == 0.62
        assert result["volume"] == 1500000.0

    def test_minimal_payload_uses_defaults(self):
        """Missing optional fields get sensible defaults."""
        result = normalize_market_payload(MINIMAL_PAYLOAD)

        assert result["source_market_id"] == "0xdef456"
        assert result["event_title"] == "Will it rain tomorrow?"
        assert result["event_category"] == ""
        assert result["best_bid"] is None
        assert result["best_ask"] is None
        # No last_trade_price, but YES token price 0.50 used as fallback
        assert result["last_price"] == 0.50
        assert result["volume"] is None

    def test_extra_fields_ignored(self):
        """Unknown fields from API changes don't cause errors."""
        result = normalize_market_payload(PAYLOAD_WITH_EXTRA_FIELDS)
        assert result["source_market_id"] == "0xabc123"

    def test_malformed_payload_raises(self):
        """Missing required field (condition_id) raises KeyError."""
        import pytest

        with pytest.raises(KeyError, match="condition_id"):
            normalize_market_payload(MALFORMED_PAYLOAD_NO_CONDITION)


# ---------------------------------------------------------------------------
# Contract tests: PolymarketAdapter (offline / stubbed)
# ---------------------------------------------------------------------------


class TestPolymarketAdapterOffline:
    """Tests that PolymarketAdapter conforms to ExternalMarketDataProvider
    protocol and correctly delegates to the HTTP client."""

    def test_implements_provider_protocol(self):
        """Adapter satisfies the ExternalMarketDataProvider protocol."""
        adapter = PolymarketAdapter(base_url="https://example.com")
        # Structural subtyping: check methods exist with correct signatures
        assert callable(getattr(adapter, "fetch_active_markets", None))
        assert callable(getattr(adapter, "fetch_market_detail", None))
        assert callable(getattr(adapter, "fetch_price_snapshot", None))

    def test_fetch_active_markets_with_respx(self):
        """Mock HTTP call and verify normalization pipeline."""
        import httpx
        import respx

        with respx.mock:
            respx.get("https://clob.polymarket.com/markets").mock(
                return_value=httpx.Response(
                    200,
                    json=[FULL_MARKET_PAYLOAD, MINIMAL_PAYLOAD],
                )
            )

            adapter = PolymarketAdapter(base_url="https://clob.polymarket.com")
            results = adapter.fetch_active_markets()

        assert len(results) == 2
        assert results[0]["source_market_id"] == "0xabc123"
        assert results[1]["source_market_id"] == "0xdef456"

    def test_fetch_market_detail_with_respx(self):
        """Mock single-market fetch."""
        import httpx
        import respx

        with respx.mock:
            respx.get("https://clob.polymarket.com/markets/0xabc123").mock(
                return_value=httpx.Response(200, json=FULL_MARKET_PAYLOAD)
            )

            adapter = PolymarketAdapter(base_url="https://clob.polymarket.com")
            result = adapter.fetch_market_detail("0xabc123")

        assert result["source_market_id"] == "0xabc123"

    def test_fetch_price_snapshot_with_respx(self):
        """Mock price snapshot fetch extracts bid/ask/last."""
        import httpx
        import respx

        with respx.mock:
            respx.get("https://clob.polymarket.com/markets/0xabc123").mock(
                return_value=httpx.Response(200, json=FULL_MARKET_PAYLOAD)
            )

            adapter = PolymarketAdapter(base_url="https://clob.polymarket.com")
            result = adapter.fetch_price_snapshot("0xabc123")

        assert result["best_bid"] == 0.60
        assert result["best_ask"] == 0.64
        assert result["last_price"] == 0.62
