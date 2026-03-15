"""Unit tests for the REST API.

Uses FastAPI's TestClient to test endpoints without a running server.
All dependencies are injected as in-memory fakes.
"""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from preddesk.domain.entities import (
    Event,
    EventStatus,
    Market,
    MarketStatus,
    MarketType,
    ModelEstimate,
    Portfolio,
    PriceSnapshot,
)
from preddesk.infrastructure.in_memory_repos import (
    InMemoryEventRepository,
    InMemoryMarketRepository,
    InMemoryModelEstimateRepository,
    InMemoryPaperOrderRepository,
    InMemoryPortfolioRepository,
    InMemoryPositionRepository,
    InMemoryPriceSnapshotRepository,
    InMemoryResearchNoteRepository,
    InMemorySignalRepository,
    InMemoryStrategyRunRepository,
    InMemoryWatchlistItemRepository,
    InMemoryWatchlistRepository,
)
from preddesk.interface.api import create_app

NOW = datetime(2025, 6, 1, 12, 0, 0, tzinfo=UTC)


def _make_app_with_data():
    """Create a test app with pre-populated data."""
    market_repo = InMemoryMarketRepository()
    event_repo = InMemoryEventRepository()
    snapshot_repo = InMemoryPriceSnapshotRepository()
    estimate_repo = InMemoryModelEstimateRepository()
    signal_repo = InMemorySignalRepository()
    order_repo = InMemoryPaperOrderRepository()
    position_repo = InMemoryPositionRepository()

    # Create test data
    event = Event(
        event_id=uuid4(),
        source_event_id="poly-1",
        title="Test Event",
        category="politics",
        status=EventStatus.OPEN,
        open_time=NOW,
    )
    event_repo.save(event)

    market = Market(
        market_id=uuid4(),
        event_id=event.event_id,
        source_market_id="mkt-1",
        market_type=MarketType.BINARY,
        venue="polymarket",
        status=MarketStatus.ACTIVE,
    )
    market_repo.save(market)

    snapshot = PriceSnapshot(
        snapshot_id=uuid4(),
        market_id=market.market_id,
        captured_at=NOW,
        best_bid=0.55,
        best_ask=0.60,
    )
    snapshot_repo.save(snapshot)

    estimate = ModelEstimate(
        estimate_id=uuid4(),
        market_id=market.market_id,
        model_name="base_rate",
        version="1.0",
        estimated_probability=0.70,
        generated_at=NOW,
    )
    estimate_repo.save(estimate)

    portfolio_repo = InMemoryPortfolioRepository()
    strategy_run_repo = InMemoryStrategyRunRepository()
    note_repo = InMemoryResearchNoteRepository()
    watchlist_repo = InMemoryWatchlistRepository()
    watchlist_item_repo = InMemoryWatchlistItemRepository()

    app = create_app(
        market_repo=market_repo,
        event_repo=event_repo,
        snapshot_repo=snapshot_repo,
        estimate_repo=estimate_repo,
        signal_repo=signal_repo,
        order_repo=order_repo,
        position_repo=position_repo,
        portfolio_repo=portfolio_repo,
        strategy_run_repo=strategy_run_repo,
        note_repo=note_repo,
        watchlist_repo=watchlist_repo,
        watchlist_item_repo=watchlist_item_repo,
    )

    return TestClient(app), market, event, snapshot, estimate


class TestHealthEndpoint:
    def test_health(self):
        app = create_app(
            market_repo=InMemoryMarketRepository(),
            event_repo=InMemoryEventRepository(),
            snapshot_repo=InMemoryPriceSnapshotRepository(),
            estimate_repo=InMemoryModelEstimateRepository(),
            signal_repo=InMemorySignalRepository(),
            order_repo=InMemoryPaperOrderRepository(),
            position_repo=InMemoryPositionRepository(),
        )
        client = TestClient(app)
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestMarketsAPI:
    def test_list_markets(self):
        client, _market, *_ = _make_app_with_data()
        r = client.get("/markets")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["venue"] == "polymarket"

    def test_get_market(self):
        client, market, *_ = _make_app_with_data()
        r = client.get(f"/markets/{market.market_id}")
        assert r.status_code == 200
        assert r.json()["source_market_id"] == "mkt-1"

    def test_get_market_not_found(self):
        client, *_ = _make_app_with_data()
        r = client.get(f"/markets/{uuid4()}")
        assert r.status_code == 404

    def test_get_market_snapshots(self):
        client, market, *_ = _make_app_with_data()
        r = client.get(f"/markets/{market.market_id}/snapshots")
        assert r.status_code == 200
        assert len(r.json()) == 1


class TestEstimatesAPI:
    def test_get_estimates(self):
        client, market, *_ = _make_app_with_data()
        r = client.get(f"/markets/{market.market_id}/estimates")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["model_name"] == "base_rate"


class TestSignalsAPI:
    def test_list_signals_empty(self):
        client, *_ = _make_app_with_data()
        r = client.get("/signals")
        assert r.status_code == 200
        assert r.json() == []


class TestPositionsAPI:
    def test_list_positions_empty(self):
        client, *_ = _make_app_with_data()
        r = client.get("/positions")
        assert r.status_code == 200
        assert r.json() == []


class TestPaperOrderPostAPI:
    """POST /paper-orders submits a simulated order through the paper broker."""

    def test_post_paper_order_buy(self):
        client, market, *_ = _make_app_with_data()
        portfolio_id = str(uuid4())
        r = client.post(
            "/paper-orders",
            json={
                "portfolio_id": portfolio_id,
                "market_id": str(market.market_id),
                "side": "BUY",
                "quantity": 5.0,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["order"]["status"] == "FILLED"
        assert data["fill"] is not None
        assert data["position"]["net_quantity"] > 0

    def test_post_paper_order_missing_market(self):
        client, *_ = _make_app_with_data()
        r = client.post(
            "/paper-orders",
            json={
                "portfolio_id": str(uuid4()),
                "market_id": str(uuid4()),
                "side": "BUY",
                "quantity": 5.0,
            },
        )
        # No snapshot → returns 404
        assert r.status_code == 404


class TestEstimateRunPostAPI:
    """POST /markets/{id}/estimates/run generates and persists an estimate."""

    def test_run_estimate(self):
        client, market, *_ = _make_app_with_data()
        r = client.post(
            f"/markets/{market.market_id}/estimates/run",
            json={
                "model_name": "base_rate",
                "successes": 7,
                "total": 10,
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["model_name"] == "base_rate"
        assert 0.0 < data["estimated_probability"] <= 1.0

    def test_run_estimate_missing_market(self):
        client, *_ = _make_app_with_data()
        r = client.post(
            f"/markets/{uuid4()}/estimates/run",
            json={"model_name": "base_rate", "successes": 5, "total": 10},
        )
        assert r.status_code == 404


class TestSignalRunPostAPI:
    """POST /signals/run detects a signal for a given market."""

    def test_run_signal(self):
        client, market, *_ = _make_app_with_data()
        r = client.post("/signals/run", json={"market_id": str(market.market_id)})
        assert r.status_code == 200
        data = r.json()
        # Should return a signal result with edge info
        assert "edge_bps" in data
        assert "is_actionable" in data

    def test_run_signal_no_estimate(self):
        """If no estimate exists for the market, return 404."""
        market_repo = InMemoryMarketRepository()
        snapshot_repo = InMemoryPriceSnapshotRepository()
        market = Market(
            market_id=uuid4(),
            event_id=uuid4(),
            source_market_id="no-est",
            market_type=MarketType.BINARY,
            venue="polymarket",
            status=MarketStatus.ACTIVE,
        )
        market_repo.save(market)
        snapshot = PriceSnapshot(
            snapshot_id=uuid4(),
            market_id=market.market_id,
            captured_at=NOW,
            best_bid=0.55,
            best_ask=0.60,
        )
        snapshot_repo.save(snapshot)
        app = create_app(
            market_repo=market_repo,
            event_repo=InMemoryEventRepository(),
            snapshot_repo=snapshot_repo,
            estimate_repo=InMemoryModelEstimateRepository(),
            signal_repo=InMemorySignalRepository(),
            order_repo=InMemoryPaperOrderRepository(),
            position_repo=InMemoryPositionRepository(),
        )
        client = TestClient(app)
        r = client.post("/signals/run", json={"market_id": str(market.market_id)})
        assert r.status_code == 404


class TestPortfolioAPI:
    def test_get_portfolio_empty(self):
        client, *_ = _make_app_with_data()
        r = client.get("/portfolio")
        assert r.status_code == 200
        assert r.json()["positions"] == []

    def test_get_portfolio_with_id(self):
        """Portfolio endpoint returns portfolio and positions for given ID."""
        portfolio_id = uuid4()
        portfolio = Portfolio(
            portfolio_id=portfolio_id,
            name="test",
            created_at=NOW,
        )
        portfolio_repo = InMemoryPortfolioRepository()
        portfolio_repo.save(portfolio)

        app = create_app(
            market_repo=InMemoryMarketRepository(),
            event_repo=InMemoryEventRepository(),
            snapshot_repo=InMemoryPriceSnapshotRepository(),
            estimate_repo=InMemoryModelEstimateRepository(),
            signal_repo=InMemorySignalRepository(),
            order_repo=InMemoryPaperOrderRepository(),
            position_repo=InMemoryPositionRepository(),
            portfolio_repo=portfolio_repo,
        )
        client = TestClient(app)
        r = client.get(f"/portfolio?portfolio_id={portfolio_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["portfolio"]["name"] == "test"


class TestBacktestAPI:
    def test_run_backtest(self):
        client, market, *_ = _make_app_with_data()
        r = client.post(
            "/backtests/run",
            json={
                "market_id": str(market.market_id),
                "strategy_name": "always_buy",
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert "total_trades" in data
        assert "metrics" in data

    def test_get_backtest_not_found(self):
        client, *_ = _make_app_with_data()
        r = client.get(f"/backtests/{uuid4()}")
        assert r.status_code == 404


class TestResearchAPI:
    def test_post_note(self):
        client, market, *_ = _make_app_with_data()
        r = client.post(
            "/notes",
            json={
                "market_id": str(market.market_id),
                "content": "Market looks overpriced.",
                "tags": ["overpriced"],
            },
        )
        assert r.status_code == 200
        data = r.json()
        assert data["content"] == "Market looks overpriced."
        assert "overpriced" in data["tags"]

    def test_post_watchlist(self):
        client, *_ = _make_app_with_data()
        r = client.post(
            "/watchlists",
            json={"name": "Weather", "description": "Weather markets"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Weather"

    def test_get_research_for_market(self):
        client, market, *_ = _make_app_with_data()
        # Add a note first
        client.post(
            "/notes",
            json={
                "market_id": str(market.market_id),
                "content": "Research note.",
            },
        )
        r = client.get(f"/research/markets/{market.market_id}")
        assert r.status_code == 200
        data = r.json()
        assert len(data["notes"]) == 1
