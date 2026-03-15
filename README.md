# PredDesk

**Prediction Markets Research Workbench**

A modular platform for prediction market research, probabilistic modeling, paper trading, and strategy backtesting.

## Overview

PredDesk is designed as a **research-first** platform that enables systematic, quantitative analysis of prediction markets. Rather than promising automated profits, it provides a rigorous laboratory for probabilistic decision-making and strategy evaluation.

### Core Capabilities

- **Market Data Ingestion**: Normalized data pipeline from prediction market providers
- **Probabilistic Modeling**: Build and compare custom probability estimates using base rates, Bayesian updates, and analyst inputs
- **Signal Generation**: Detect opportunities by comparing market prices against model estimates
- **Paper Trading**: Simulate trades with realistic fees, slippage, and position sizing
- **Backtesting**: Evaluate strategies on historical data with proper temporal discipline
- **Research Workspace**: Document hypotheses, tag markets, and maintain audit trails

## Philosophy

**Phase 1 Focus**: Research, simulation, and learning — no real money execution.

The platform adheres to strict principles:
- **Research before automation**
- **Simulation before real risk**
- **Explainability before sophistication**
- **Data integrity before exotic features**

## Architecture

PredDesk follows clean/hexagonal architecture with:
- **Domain layer**: Core entities, value objects, and business rules
- **Application layer**: Use cases and orchestration
- **Infrastructure layer**: External adapters, persistence, HTTP clients
- **Interface layer**: REST API and web UI

All critical financial logic (probability calculations, EV estimation, Kelly sizing, PnL accounting) is designed for high test coverage and pedagogical clarity.

## Technology Stack

- **Backend**: Python 3.13+, FastAPI, Pydantic v2
- **Persistence**: PostgreSQL + SQLAlchemy 2.0
- **Testing**: pytest with property-based testing (Hypothesis)
- **Frontend**: Next.js / React + TypeScript
- **Package Management**: `uv` for all Python dependencies

## Project Structure

```
preddesk/
├── src/preddesk/
│   ├── domain/          # Core business logic
│   ├── application/     # Use cases
│   ├── infrastructure/  # External adapters
│   └── interface/       # API & UI
├── tests/
│   ├── unit/
│   ├── property/
│   ├── integration/
│   └── e2e/
├── docs/
│   ├── adr/            # Architecture decision records
│   ├── domain/         # Domain documentation
│   └── math/           # Mathematical foundations
├── migrations/
└── scripts/
```

## Key Concepts

### Domain Model

- **Events & Markets**: Real-world events and their tradable instruments
- **Price Snapshots**: Observable market state at points in time
- **Model Estimates**: Probabilistic assessments with uncertainty bounds
- **Signals**: Detected opportunities with explicit edge calculations
- **Paper Orders/Fills**: Simulated executions with realistic costs
- **Positions & Portfolio**: Aggregated holdings and PnL tracking

### Probabilistic Models

- **Implied Probability**: Market-derived baseline
- **Base-Rate Model**: Historical frequency estimates
- **Bayesian Updater**: Prior + evidence → posterior
- **Analyst Override**: Structured subjective estimates

### Risk & Sizing

- Fixed unit sizing
- Fixed dollar risk
- Fractional Kelly (capped conservatively)

**Note**: Full Kelly is never used as default due to estimation risk.

## Testing Philosophy

PredDesk treats tests as **executable documentation**. Critical financial logic includes:
- Mathematical explanations of formulas and identities
- Pedagogical examples with concrete numbers
- Property-based tests for invariants
- Integration tests with real PostgreSQL (testcontainers)

Target coverage: 85%+ overall, 95%+ on domain logic.

## Development Setup

_(Coming soon)_

Prerequisites:
- Python 3.13 (via Homebrew)
- PostgreSQL 14+
- `uv` for package management

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Start local environment
docker-compose up -d
```

## Roadmap

### Phase 1: Foundation (Current)
- Market ingestion & normalization
- Probability modeling
- Signal generation
- Paper trading
- Backtesting engine
- Research workspace

### Phase 2: Strategy Lab
- Multi-source data fusion
- Advanced backtesting
- Pluggable strategy framework
- Risk dashboards

### Phase 3: Assisted Execution
- Pre-trade validation
- Manual approval flows
- Live order routing prep

### Phase 4: Selective Automation
- Conditional real execution (feature-flagged)
- Strict risk limits
- Kill switches

## Non-Goals (Phase 1)

- Real money execution
- Multi-exchange arbitrage
- Ultra-low latency trading
- Market making
- Complex ML in production
- LLM-dependent core logic
- Crypto custody / smart contracts

## Contributing

_(Guidelines coming soon)_

## License

_(To be determined)_

---

**Built with disciplined architecture, rigorous testing, and respect for uncertainty.**
