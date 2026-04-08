# AgentBond Product Roadmap

Last updated: 2026-04-08

## Completed

### Core Protocol (Shipped)
- UUPS-upgradeable smart contracts on Base Sepolia (AgentRegistry, PolicyRegistry, WarrantyPool, ClaimManager, Heartbeat)
- Full agent lifecycle: register → policy → stake → execute → claim → slash → reimburse
- TEE-attested inference via OpenGradient SDK with x402 settlement on Base Sepolia
- Deterministic policy engine with 6 rule types (tool whitelist, value cap, prohibited targets, frequency, data freshness, model mismatch)
- Evidence hashing for independent run replay and verification
- `verified` field on every run — explicitly marks whether execution was TEE-attested or mock

### Security & Auth (Shipped)
- SHA-256 hashed API keys (plaintext never stored)
- Wallet signature auth on agent registration and claim submission (EIP-191)
- Operator API key required for run execution (with agent ownership verification)
- Per-operator rate limiting (30 rpm) + global IP rate limiting (120 rpm)
- Daily claim circuit breaker (5 per claimant per day)
- HMAC-SHA256 signed webhook payouts with exponential backoff retries

### Smart Contract Security (Shipped)
- Fixed unstake accounting (pendingUnstake tracked separately — collateral can't be drained during cooldown)
- Resolver/pool-initiated pauses can't be overridden by operators
- Heartbeat operator authentication (no liveness spoofing)
- Zero-address checks, admin change events, agent existence validation on claims
- UUPS upgradeability for all core contracts

### Frontend & UX (Shipped)
- React + TypeScript + Vite dashboard with Tailwind CSS v4
- Live SSE streaming during run execution (memory → inference → policy → done)
- Agent memory panel with run history
- Score history charts
- MetaMask wallet integration for on-chain flows
- Operator console: register → policy → stake → execute

### Observability (Shipped)
- Prometheus metrics (HTTP, runs, claims, webhooks, rate limits)
- Structured JSON logging
- Webhook delivery audit trail
- Agent memory system (success/violation/context types)

### Testing (Shipped)
- 103 backend tests (unit, integration, e2e)
- 45 Hardhat contract tests (including upgradeability)
- 74 frontend tests
- CI pipeline (GitHub Actions)

---

## Phase 1 — Production Hardening (Current)
- Pydantic response models on all API endpoints
- TypeScript interfaces for all domain types (eliminate `any`)
- Responsive design (mobile-friendly)
- Multi-wallet support (wagmi + RainbowKit)
- Database indexes on hot query paths
- Alembic as sole schema source of truth
- Domain + HTTPS for backend API

## Phase 2 — Trust & Transparency
- Resolver timelock + multisig documentation
- Public landing page with product explainer
- Reputation scoring unit tests and tuning
- Failing-agent lifecycle E2E test
- Variable claim amounts based on severity
- Claim bond system (claimant deposits forfeit on rejection)

## Phase 3 — Scale & Adoption
- Multi-chain contract deployment
- Mainnet readiness audit
- Operator onboarding documentation
- SDK for third-party integrations
- Governance framework for resolver selection

## Milestones

**M1 — Production-Ready API** (Phase 1)
- All endpoints have Pydantic response schemas
- Frontend is responsive on mobile
- Backend runs behind domain + HTTPS

**M2 — Verifiable Trust** (Phase 2)
- Resolver operates under timelock
- Reputation formula is tested and documented
- Landing page converts visitors to operators

**M3 — Mainnet Launch** (Phase 3)
- Security audit complete
- Multi-chain deployment tested
- 5+ operators onboarded in pilot
