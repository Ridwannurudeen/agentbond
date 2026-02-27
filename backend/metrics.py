"""Prometheus metrics definitions for AgentBond."""

from prometheus_client import Counter, Histogram, Gauge, Info

# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

HTTP_REQUESTS_TOTAL = Counter(
    "agentbond_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

HTTP_REQUEST_DURATION = Histogram(
    "agentbond_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

RATE_LIMIT_HITS_TOTAL = Counter(
    "agentbond_rate_limit_hits_total",
    "Number of requests rejected by rate limiter",
)

# ---------------------------------------------------------------------------
# Business — runs
# ---------------------------------------------------------------------------

RUNS_TOTAL = Counter(
    "agentbond_runs_total",
    "Total agent runs executed",
    ["verdict"],          # "pass" | "fail"
)

RUN_DURATION = Histogram(
    "agentbond_run_duration_seconds",
    "Agent run execution latency (OG SDK + policy evaluation)",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
)

# ---------------------------------------------------------------------------
# Business — claims
# ---------------------------------------------------------------------------

CLAIMS_TOTAL = Counter(
    "agentbond_claims_total",
    "Total warranty claims submitted",
    ["status"],           # "submitted" | "approved" | "rejected" | "paid"
)

# ---------------------------------------------------------------------------
# Business — webhooks
# ---------------------------------------------------------------------------

WEBHOOK_DELIVERIES_TOTAL = Counter(
    "agentbond_webhook_deliveries_total",
    "Total webhook delivery attempts",
    ["event_type", "success"],   # success: "true" | "false"
)

WEBHOOK_DURATION = Histogram(
    "agentbond_webhook_duration_seconds",
    "Webhook HTTP POST latency per attempt",
    ["event_type"],
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# ---------------------------------------------------------------------------
# Service info
# ---------------------------------------------------------------------------

SERVICE_INFO = Info(
    "agentbond_service",
    "AgentBond service metadata",
)
SERVICE_INFO.info({"version": "0.1.0", "chain": "base-sepolia"})
