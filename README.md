# AgentBond - Verifiable Agent Warranty Network

On-chain warranty layer on OpenGradient where operators stake collateral, agent executions are verifiably attested, policy violations are deterministically detected, and breaches trigger automatic slashing + user reimbursement.

## Architecture

- **Smart Contracts** (Solidity): AgentRegistry, PolicyRegistry, WarrantyPool, ClaimManager, Heartbeat
- **Backend** (FastAPI): Agent orchestration, policy engine, claim verification, reputation scoring
- **Frontend** (React): Unified dashboard for operators and users
- **CLI** (Click): Operator management tool
- **Chain**: OpenGradient Testnet (ChainID: 10740, RPC: https://ogevmdevnet.opengradient.ai)

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+

### Setup

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Install frontend dependencies
cd frontend && npm install && cd ..

# Install contract dependencies
cd contracts && npm install && cd ..

# Start backend (uses SQLite by default)
make dev

# In another terminal, run frontend
make frontend
```

### Seed Demo Data

```bash
# Ensure backend is running, then:
make seed
```

Creates 3 demo agents (Finance, Research, Trading) with policies and staked collateral.

### Run End-to-End Demo

```bash
make demo
```

Full lifecycle: register agent → strict policy → stake → clean run (pass) → violating run (fail) → claim submission → auto-verification → score degradation.

### Docker (Optional)

```bash
cp .env.example .env
# Edit .env with your keys
docker compose up -d
```

## Smart Contracts

5 contracts deployed on OpenGradient testnet:

| Contract | Purpose |
|----------|---------|
| `AgentRegistry` | Agent registration, versioning, reputation, operator/resolver access control |
| `PolicyRegistry` | Policy definitions, activation, deprecation |
| `WarrantyPool` | Staking (7-day cooldown unstake), slashing, payouts, auto-pause |
| `ClaimManager` | Claim lifecycle (submit/verify/approve/reject/pay), rate limiting |
| `Heartbeat` | On-chain liveness proof (1-hour threshold ping/isAlive/getStatus) |

Compile and test:

```bash
cd contracts
npx hardhat compile
npx hardhat test      # 28 tests
```

Deploy to OpenGradient testnet:

```bash
python scripts/deploy.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/agents` | Register agent |
| GET | `/api/agents` | List agents |
| GET | `/api/agents/{id}` | Get agent details |
| POST | `/api/agents/{id}/versions` | Publish version |
| POST | `/api/agents/{id}/stake` | Stake collateral |
| POST | `/api/agents/{id}/unstake` | Request unstake |
| POST | `/api/agents/{id}/webhook` | Configure operator webhook |
| POST | `/api/policies` | Register policy |
| GET | `/api/policies/{id}` | Get policy |
| POST | `/api/policies/{id}/activate` | Activate policy |
| POST | `/api/runs` | Execute agent run |
| GET | `/api/runs/{id}` | Get run details |
| GET | `/api/runs/{id}/replay` | Re-verify run |
| POST | `/api/claims` | Submit claim |
| GET | `/api/claims/{id}` | Get claim status |
| GET | `/api/scores/{agentId}` | Get trust score |
| GET | `/api/scores` | List all scores |
| GET | `/api/dashboard/stats` | Global stats |
| POST | `/api/operators/{wallet}/api-key` | Generate API key |

### Authentication

API key authentication is optional for MVP. Generate a key:

```bash
curl -X POST http://localhost:8000/api/operators/0xYOUR_WALLET/api-key
```

Include in requests via `X-API-Key` header:

```bash
curl -H "X-API-Key: YOUR_KEY" http://localhost:8000/api/agents
```

### Rate Limiting

120 requests per minute per IP address. Exceeding returns HTTP 429.

### Webhooks

Operators can register a webhook URL to receive notifications for:

- `claim.submitted` — when a claim is filed against their agent
- `claim.resolved` — when a claim is approved or rejected
- `score.changed` — when their agent's trust score changes

Configure via:

```bash
curl -X POST http://localhost:8000/api/agents/{id}/webhook \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "https://your-server.com/hook"}'
```

## Database Migrations

Uses Alembic for schema migrations:

```bash
# Generate a new migration after model changes
python -m alembic revision --autogenerate -m "description"

# Apply migrations
python -m alembic upgrade head

# Rollback one step
python -m alembic downgrade -1
```

## CLI Usage

```bash
# Register an agent
agentbond agent register --wallet 0x... --metadata-uri ipfs://...

# List agents
agentbond agent list

# Register a policy
agentbond policy register 1 --rules-file policy.json

# Execute a run
agentbond run execute 1 --input "What is the price of ETH?"

# Submit a claim
agentbond claim submit <run_id> 1 --claimant 0x... --reason TOOL_WHITELIST_VIOLATION

# Check score
agentbond score get 1

# Dashboard stats
agentbond stats
```

## Policy Rules (JSON)

```json
{
  "allowed_tools": ["get_price", "get_portfolio"],
  "prohibited_targets": ["0xdead..."],
  "max_value_per_action": 1000,
  "max_actions_per_window": 100,
  "window_seconds": 3600,
  "required_data_freshness_seconds": 300
}
```

## Reason Codes

| Code | Description | Auto-verifiable |
|------|-------------|-----------------|
| TOOL_WHITELIST_VIOLATION | Used tool not in policy | Yes |
| VALUE_LIMIT_EXCEEDED | Action exceeded max value | Yes |
| PROHIBITED_TARGET | Interacted with blocked address | Yes |
| FREQUENCY_EXCEEDED | Too many actions in window | Yes |
| STALE_DATA | Data older than freshness requirement | Yes |
| MODEL_MISMATCH | Declared model != executed model | Yes |

## Testing

```bash
# All backend tests (74 tests)
make test

# Contract tests (28 tests)
make contracts-test

# Run specific test file
python -m pytest tests/test_policy_engine.py -v
```

## Project Structure

```
agentbond/
├── contracts/               # Solidity smart contracts + Hardhat
│   ├── src/                 # .sol files (AgentRegistry, PolicyRegistry, etc.)
│   └── test/                # Hardhat tests
├── backend/                 # FastAPI application
│   ├── routers/             # API route handlers
│   ├── services/            # Business logic (policy engine, orchestrator, etc.)
│   ├── models/              # SQLAlchemy models
│   ├── contracts/           # Web3 contract interface
│   ├── auth.py              # API key authentication
│   ├── middleware.py         # Rate limiting
│   ├── validation.py        # Input validation utilities
│   └── config.py            # Settings (DB URL, chain config)
├── frontend/                # React dashboard (Vite + TypeScript)
│   └── src/pages/           # Dashboard, AgentDetail, RunDetail, Claims, Operator
├── cli/                     # Click-based CLI tool
├── alembic/                 # Database migrations
├── scripts/                 # Deploy, seed, demo scripts
├── tests/                   # Python tests
├── docker-compose.yml       # Full-stack dev setup
├── Makefile                 # Common commands
└── pyproject.toml           # Python dependencies
```

## License

MIT
