# AgentBond — Verifiable Agent Warranty Network

[![CI](https://github.com/Ridwannurudeen/agentbond/actions/workflows/ci.yml/badge.svg)](https://github.com/Ridwannurudeen/agentbond/actions/workflows/ci.yml)

On-chain warranty layer where operators stake collateral, agent executions are verifiably attested via OpenGradient TEE inference, policy violations are deterministically detected, and breaches trigger automatic slashing and user reimbursement.

**Live:** Backend on VPS (`http://75.119.153.252/api`) · Frontend on Vercel (`https://frontend-omega-jet-65.vercel.app`)

## Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Smart Contracts | Solidity + Hardhat | On-chain registry, staking, claim settlement |
| Backend | FastAPI + SQLAlchemy async | Orchestration, policy engine, claim verification, scoring |
| AI Inference | OpenGradient SDK (TEE) | Verifiable LLM execution with x402 settlement on Base Sepolia |
| Agent Memory | PostgreSQL + Alembic | Per-agent run history injected into LLM context |
| Frontend | React + TypeScript + Vite | Operator and user dashboard with live SSE streaming |
| CLI | Click | Operator management from the terminal |
| Chain | Base Sepolia (chain 84532) | Deployed contracts |

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 20+

### Setup

```bash
# Install all dependencies
make install

# Apply database migrations
make db-migrate

# Start backend (SQLite by default, port 8000)
make dev

# In another terminal, start frontend (port 5173)
make frontend
```

### Seed Demo Data

```bash
# With backend running:
make seed
```

Creates 3 demo agents (Finance, Research, Trading) with policies and staked collateral.

### Run End-to-End Demo

```bash
make demo
```

Full lifecycle: register agent → strict policy → stake → clean run (pass) → violating run (fail) → claim submission → auto-verification → score degradation.

### Docker (Full Stack)

```bash
cp .env.example .env
# Edit .env with your keys
docker compose up -d
```

Starts PostgreSQL, backend, and frontend. Backend at `http://localhost:8000`, frontend at `http://localhost:3000`.

## Smart Contracts

4 contracts deployed on **Base Sepolia** (chain ID 84532):

| Contract | Purpose |
|----------|---------|
| `AgentRegistry` | Agent registration, versioning, reputation scores, operator/resolver access control |
| `PolicyRegistry` | Policy definitions, activation, deprecation |
| `WarrantyPool` | Staking (7-day cooldown unstake), slashing, payouts, collateral reservation |
| `ClaimManager` | Claim lifecycle (submit → verify → approve/reject → payout), daily rate limiting |

```bash
# Compile
cd contracts && npx hardhat compile

# Run Hardhat tests (28 tests)
cd contracts && npx hardhat test

# Deploy (requires .env with private key and RPC)
python scripts/deploy.py
```

## API Reference

### Authentication

Write endpoints require an API key in the `X-API-Key` header.

Generate one:

```bash
curl -X POST http://localhost:8000/api/operators/0xYOUR_WALLET/api-key
```

**First call:** unauthenticated (no key exists yet).
**Subsequent rotation:** current key must be present in `X-API-Key`.

### Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/api/health` | — | Health check + DB status |
| GET | `/metrics` | — | Prometheus metrics |
| POST | `/api/agents` | — | Register agent (creates operator if new) |
| GET | `/api/agents` | — | List all agents |
| GET | `/api/agents/{id}` | — | Get agent details |
| POST | `/api/agents/{id}/versions` | ✓ | Publish new version hash |
| POST | `/api/agents/{id}/status` | ✓ | Update agent status |
| POST | `/api/agents/{id}/webhook` | ✓ | Configure webhook URL |
| POST | `/api/agents/{id}/stake` | ✓ | Stake collateral |
| POST | `/api/agents/{id}/unstake` | ✓ | Request unstake (7-day cooldown) |
| GET | `/api/agents/{id}/memories` | — | List agent memories (supports `?limit=N&memory_type=`) |
| POST | `/api/agents/{id}/memories` | ✓ | Add operator context memory |
| POST | `/api/policies` | ✓ | Register policy |
| GET | `/api/policies/{id}` | — | Get policy |
| POST | `/api/policies/{id}/activate` | ✓ | Activate policy for agent |
| POST | `/api/runs` | — | Execute agent run |
| POST | `/api/runs/stream` | — | Execute run with live SSE progress events |
| GET | `/api/runs` | — | List runs (filter by agent_id) |
| GET | `/api/runs/{id}` | — | Get run details |
| GET | `/api/runs/{id}/replay` | — | Re-verify run proof |
| POST | `/api/claims` | — | Submit claim |
| GET | `/api/claims/{id}` | — | Get claim status |
| GET | `/api/scores/{agentId}` | — | Get agent trust score breakdown |
| GET | `/api/scores/{agentId}/history` | — | Score snapshot history |
| GET | `/api/scores` | — | Global dashboard stats |
| POST | `/api/operators/{wallet}/api-key` | — | Generate operator API key |
| GET | `/api/operators/{id}/webhook-deliveries` | ✓ | Webhook delivery history |

### Rate Limiting

- **Global:** 120 requests/minute per IP
- **Per-operator:** 30 requests/minute per API key (when `X-API-Key` header is present)

Returns HTTP 429 when exceeded.

### Claim Circuit Breaker

Maximum **5 claims per claimant address per UTC day**. Returns HTTP 429 on breach.

## Agent Memory

Every run automatically stores a memory record (`success` or `violation`) for the agent. Operators can also inject custom `context` memories. The last 10 memories are prepended to the LLM prompt on each subsequent run, giving the agent behavioural continuity.

```bash
# List memories
curl http://localhost:8000/api/agents/1/memories

# Filter by type
curl "http://localhost:8000/api/agents/1/memories?memory_type=violation&limit=5"

# Add operator context
curl -X POST http://localhost:8000/api/agents/1/memories \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"content": "Prefer low-risk ETH trades.", "metadata": {"source": "operator"}}'
```

Memory types:

| Type | Created by | Description |
|------|-----------|-------------|
| `success` | System | Run passed all policy checks |
| `violation` | System | Run failed policy — stores reason codes |
| `context` | Operator | Custom instructions injected into future runs |

## SSE Streaming

Use `/api/runs/stream` to receive live progress events during a run:

```bash
curl -X POST http://localhost:8000/api/runs/stream \
  -H "Content-Type: application/json" \
  -d '{"agent_id": 1, "user_input": "What is the price of ETH?"}'
```

Events emitted in order:

| Event | Data |
|-------|------|
| `memory_loaded` | `has_context`, `agent_id` |
| `inference_start` | `model`, `agent_id` |
| `inference_done` | `output`, `settlement_tx` |
| `policy_evaluated` | `verdict`, `reason_codes` |
| `complete` | Full run result |
| `error` | `message` |

## Policy Rules

Define constraints as JSON when registering a policy:

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

### Reason Codes

| Code | Description | Auto-verifiable |
|------|-------------|:--------------:|
| `TOOL_WHITELIST_VIOLATION` | Used tool not in policy | ✓ |
| `VALUE_LIMIT_EXCEEDED` | Action exceeded max value | ✓ |
| `PROHIBITED_TARGET` | Interacted with blocked address | ✓ |
| `FREQUENCY_EXCEEDED` | Too many actions in time window | ✓ |
| `STALE_DATA` | Data older than freshness requirement | ✓ |
| `MODEL_MISMATCH` | Declared model != executed model | ✓ |

## Webhooks

Operators receive real-time event notifications via HMAC-SHA256 signed POST requests (up to 3 retries with exponential backoff). Configure a webhook URL:

```bash
curl -X POST http://localhost:8000/api/agents/1/webhook \
  -H "X-API-Key: YOUR_KEY" \
  -H "Content-Type: application/json" \
  -d '{"webhook_url": "https://your-server.com/hook"}'
```

### Events

| Event | Trigger |
|-------|---------|
| `claim.submitted` | A claim is filed against the agent |
| `claim.resolved` | A claim is approved or rejected |
| `score.changed` | The agent's trust score changes |

### Payload Format

```json
{
  "event": "claim.submitted",
  "agent_id": 1,
  "operator_id": 1,
  "timestamp": "2026-01-01T00:00:00Z",
  "data": { ... }
}
```

Verify authenticity using the `X-AgentBond-Signature: sha256=<hex>` header (HMAC-SHA256 keyed with your API key).

## Monitoring

The backend exposes a Prometheus-compatible `/metrics` endpoint and emits structured JSON logs.

### Key Metrics

| Metric | Type | Labels |
|--------|------|--------|
| `agentbond_http_requests_total` | Counter | method, path, status |
| `agentbond_http_request_duration_seconds` | Histogram | method, path |
| `agentbond_runs_total` | Counter | verdict (pass/fail) |
| `agentbond_run_duration_seconds` | Histogram | — |
| `agentbond_claims_total` | Counter | status (submitted/approved/rejected) |
| `agentbond_webhook_deliveries_total` | Counter | event_type, success |
| `agentbond_rate_limit_hits_total` | Counter | — |

### Log Format

```json
{"ts": "2026-01-01T00:00:00Z", "level": "INFO", "logger": "backend.services.orchestrator", "msg": "Run completed", "verdict": "pass"}
```

## Database Migrations

```bash
# Apply pending migrations
make db-migrate

# Generate migration after model changes
python -m alembic revision --autogenerate -m "description"

# Roll back one step
python -m alembic downgrade -1
```

## CLI

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

# Check trust score
agentbond score get 1

# Dashboard stats
agentbond stats
```

## Testing

```bash
# Backend — 152 tests (unit, integration, contract)
make test

# Hardhat contract tests — 28 tests
make contracts-test

# Frontend — 74 tests
cd frontend && npm test

# With coverage
cd frontend && npm run test:coverage
```

### Test layout

```
tests/
├── test_auth.py            # API key generation and enforcement
├── test_claim_verifier.py  # Claim reason code logic
├── test_e2e.py             # Full lifecycle via TestClient
├── test_memory.py          # Memory service + API endpoints (22 tests)
├── test_middleware.py      # Rate limiting (IP + per-operator)
├── test_orchestrator.py    # OG execution client (mock mode)
├── test_policy_engine.py   # All 6 policy rule types
├── test_validation.py      # Input validation
├── test_webhooks.py        # Webhook delivery and helpers
└── test_contracts/         # In-process EVM tests (eth-tester + py-evm)
    ├── test_agent_registry.py    # 16 tests
    ├── test_policy_registry.py   # 11 tests
    ├── test_warranty_pool.py     # 13 tests
    └── test_claim_manager.py     # 16 tests

frontend/src/__tests__/
├── api.test.ts             # 18 tests — all API helper functions
├── AgentDetail.test.tsx    # 14 tests — SSE streaming UI, memory panel
├── Dashboard.test.tsx      # 13 tests — stat cards, agent table, recent runs
├── memory.test.ts          # 10 tests — fetchAgentMemories, streamRun
├── Runs.test.tsx           # 12 tests — filtering, refresh, agent filter
└── WalletContext.test.tsx  #  7 tests — MetaMask connect/disconnect flow
```

## Project Structure

```
agentbond/
├── contracts/               # Solidity contracts + Hardhat
│   ├── src/                 # AgentRegistry.sol, PolicyRegistry.sol, WarrantyPool.sol, ClaimManager.sol
│   └── test/                # Hardhat test suite
├── backend/
│   ├── routers/             # agents.py, runs.py, claims.py, policies.py, scores.py, operators.py
│   ├── services/            # orchestrator.py, og_client.py, policy_engine.py, claim_verifier.py,
│   │                        # webhooks.py, reputation.py, memory.py
│   ├── models/              # SQLAlchemy schema (Agent, Run, Claim, AgentMemory, ...)
│   ├── contracts/           # Web3 contract interface
│   ├── auth.py              # require_operator_key dependency
│   ├── middleware.py        # RateLimitMiddleware, MetricsMiddleware
│   ├── metrics.py           # Prometheus metric definitions
│   ├── logging_setup.py     # JsonFormatter for structured logging
│   └── config.py            # Pydantic settings
├── frontend/
│   └── src/
│       ├── pages/           # Dashboard, Runs, RunDetail, Claims, AgentDetail, Operator
│       ├── context/         # WalletContext (MetaMask integration)
│       └── __tests__/       # Vitest test suite
├── cli/                     # Click CLI (agentbond command)
├── alembic/                 # Migration scripts
├── scripts/                 # deploy.py, seed.py, demo_run.py
├── tests/                   # Python test suite
├── docker-compose.yml
├── Dockerfile.backend
├── Makefile
└── pyproject.toml
```

## License

MIT
