# AgentBond - Verifiable Agent Warranty Network

On-chain warranty layer on OpenGradient where operators stake collateral, agent executions are verifiably attested, policy violations are deterministically detected, and breaches trigger automatic slashing + user reimbursement.

## Architecture

- **Smart Contracts** (Solidity): AgentRegistry, PolicyRegistry, WarrantyPool, ClaimManager
- **Backend** (FastAPI): Agent orchestration, policy engine, claim verification, reputation scoring
- **Frontend** (React): Unified dashboard for operators and users
- **CLI** (Click): Operator management tool
- **Chain**: OpenGradient Testnet (ChainID: 131072)

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL (or use Docker)

### Option 1: Docker (Recommended)

```bash
cp .env.example .env
# Edit .env with your keys
docker compose up -d
```

### Option 2: Manual Setup

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Install frontend dependencies
cd frontend && npm install && cd ..

# Install contract dependencies
cd contracts && npm install && cd ..

# Start PostgreSQL (or use Docker)
docker compose up -d postgres

# Run backend
make dev

# In another terminal, run frontend
make frontend
```

### Seed Demo Data

```bash
# Ensure backend is running, then:
make seed
```

This creates 3 demo agents with policies and staked collateral.

### Run End-to-End Demo

```bash
make demo
```

Walks through: register agent -> stake -> execute run -> submit claim -> verify -> check scores.

## Smart Contracts

Compile and test:

```bash
cd contracts
npm install
npx hardhat compile
npx hardhat test
```

Deploy to OpenGradient testnet:

```bash
python scripts/deploy.py
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/agents` | Register agent |
| GET | `/api/agents/{id}` | Get agent details |
| POST | `/api/agents/{id}/versions` | Publish version |
| POST | `/api/agents/{id}/stake` | Stake collateral |
| POST | `/api/agents/{id}/unstake` | Request unstake |
| POST | `/api/policies` | Register policy |
| GET | `/api/policies/{id}` | Get policy |
| POST | `/api/policies/{id}/activate` | Activate policy |
| POST | `/api/runs` | Execute agent run |
| GET | `/api/runs/{id}` | Get run details |
| GET | `/api/runs/{id}/replay` | Re-verify run |
| POST | `/api/claims` | Submit claim |
| GET | `/api/claims/{id}` | Get claim status |
| GET | `/api/scores/{agentId}` | Get trust score |
| GET | `/api/dashboard/stats` | Global stats |

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

| Code | Description |
|------|-------------|
| TOOL_WHITELIST_VIOLATION | Used tool not in policy |
| VALUE_LIMIT_EXCEEDED | Action exceeded max value |
| PROHIBITED_TARGET | Interacted with blocked address |
| FREQUENCY_EXCEEDED | Too many actions in window |
| STALE_DATA | Data older than freshness requirement |
| MODEL_MISMATCH | Declared model != executed model |

## Testing

```bash
# Backend tests
make test

# Contract tests
make contracts-test
```

## Project Structure

```
agentbond/
├── contracts/           # Solidity smart contracts + Hardhat
├── backend/             # FastAPI application
│   ├── routers/         # API route handlers
│   ├── services/        # Business logic (policy engine, orchestrator, etc.)
│   ├── models/          # SQLAlchemy models
│   └── contracts/       # Web3 contract interface
├── frontend/            # React dashboard
├── cli/                 # Click-based CLI tool
├── scripts/             # Deploy, seed, demo scripts
└── tests/               # Python tests
```
