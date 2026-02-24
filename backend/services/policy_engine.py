"""Deterministic policy rule evaluation engine.

All functions are pure -- no side effects, no DB access, no network calls.
Each returns a RuleResult indicating pass/fail with evidence.
"""

import time
from dataclasses import dataclass, field


@dataclass
class RuleResult:
    passed: bool
    reason_code: str
    evidence: dict = field(default_factory=dict)


@dataclass
class PolicyVerdict:
    passed: bool
    results: list[RuleResult]
    failed_codes: list[str]
    evidence_hash: str


def check_tool_whitelist(transcript: list[dict], policy: dict) -> RuleResult:
    """Check that all tool calls are in the allowed_tools list."""
    allowed = set(policy.get("allowed_tools", []))
    if not allowed:
        return RuleResult(passed=True, reason_code="TOOL_WHITELIST_VIOLATION")

    violations = []
    for entry in transcript:
        if entry.get("role") == "tool_call":
            tool = entry.get("tool", "")
            if tool and tool not in allowed:
                violations.append(tool)

    if violations:
        return RuleResult(
            passed=False,
            reason_code="TOOL_WHITELIST_VIOLATION",
            evidence={"disallowed_tools": violations, "allowed": list(allowed)},
        )
    return RuleResult(passed=True, reason_code="TOOL_WHITELIST_VIOLATION")


def check_value_limits(transcript: list[dict], policy: dict) -> RuleResult:
    """Check that no single action exceeds max_value_per_action."""
    max_value = policy.get("max_value_per_action")
    if max_value is None:
        return RuleResult(passed=True, reason_code="VALUE_LIMIT_EXCEEDED")

    violations = []
    for entry in transcript:
        if entry.get("role") == "tool_call":
            args = entry.get("args", {})
            value = args.get("value", args.get("amount", 0))
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if value > max_value:
                violations.append({"tool": entry.get("tool"), "value": value, "max": max_value})

    if violations:
        return RuleResult(
            passed=False,
            reason_code="VALUE_LIMIT_EXCEEDED",
            evidence={"violations": violations},
        )
    return RuleResult(passed=True, reason_code="VALUE_LIMIT_EXCEEDED")


def check_prohibited_targets(transcript: list[dict], policy: dict) -> RuleResult:
    """Check that no action targets a prohibited address."""
    prohibited = set(t.lower() for t in policy.get("prohibited_targets", []))
    if not prohibited:
        return RuleResult(passed=True, reason_code="PROHIBITED_TARGET")

    violations = []
    for entry in transcript:
        if entry.get("role") == "tool_call":
            args = entry.get("args", {})
            target = args.get("target", args.get("to", args.get("address", "")))
            if isinstance(target, str) and target.lower() in prohibited:
                violations.append({"tool": entry.get("tool"), "target": target})

    if violations:
        return RuleResult(
            passed=False,
            reason_code="PROHIBITED_TARGET",
            evidence={"violations": violations, "prohibited": list(prohibited)},
        )
    return RuleResult(passed=True, reason_code="PROHIBITED_TARGET")


def check_action_frequency(
    run_history: list[dict], policy: dict
) -> RuleResult:
    """Check that action count within window doesn't exceed max."""
    max_actions = policy.get("max_actions_per_window")
    window = policy.get("window_seconds")
    if max_actions is None or window is None:
        return RuleResult(passed=True, reason_code="FREQUENCY_EXCEEDED")

    now = time.time()
    cutoff = now - window
    recent_count = sum(
        1 for run in run_history
        if run.get("timestamp", 0) >= cutoff
    )

    if recent_count > max_actions:
        return RuleResult(
            passed=False,
            reason_code="FREQUENCY_EXCEEDED",
            evidence={
                "count": recent_count,
                "max": max_actions,
                "window_seconds": window,
            },
        )
    return RuleResult(passed=True, reason_code="FREQUENCY_EXCEEDED")


def check_data_freshness(run_metadata: dict, policy: dict) -> RuleResult:
    """Check that data sources used are within freshness requirement."""
    max_staleness = policy.get("required_data_freshness_seconds")
    if max_staleness is None:
        return RuleResult(passed=True, reason_code="STALE_DATA")

    now = time.time()
    data_sources = run_metadata.get("data_sources", [])
    stale = []
    for source in data_sources:
        ts = source.get("timestamp", 0)
        age = now - ts
        if age > max_staleness:
            stale.append({
                "source": source.get("name", "unknown"),
                "age_seconds": age,
                "max_seconds": max_staleness,
            })

    if stale:
        return RuleResult(
            passed=False,
            reason_code="STALE_DATA",
            evidence={"stale_sources": stale},
        )
    return RuleResult(passed=True, reason_code="STALE_DATA")


def check_model_mismatch(run_metadata: dict, policy: dict) -> RuleResult:
    """Check that the executed model matches the declared model."""
    declared = run_metadata.get("declared_model")
    executed = run_metadata.get("executed_model")

    if not declared or not executed:
        return RuleResult(passed=True, reason_code="MODEL_MISMATCH")

    if declared != executed:
        return RuleResult(
            passed=False,
            reason_code="MODEL_MISMATCH",
            evidence={"declared": declared, "executed": executed},
        )
    return RuleResult(passed=True, reason_code="MODEL_MISMATCH")


def evaluate_policy(
    transcript: list[dict],
    policy: dict,
    run_history: list[dict] | None = None,
    run_metadata: dict | None = None,
) -> PolicyVerdict:
    """Run all policy checks and return aggregate verdict."""
    import hashlib, json

    run_history = run_history or []
    run_metadata = run_metadata or {}

    results = [
        check_tool_whitelist(transcript, policy),
        check_value_limits(transcript, policy),
        check_prohibited_targets(transcript, policy),
        check_action_frequency(run_history, policy),
        check_data_freshness(run_metadata, policy),
        check_model_mismatch(run_metadata, policy),
    ]

    failed = [r for r in results if not r.passed]
    failed_codes = [r.reason_code for r in failed]

    # Deterministic evidence hash
    evidence_data = json.dumps(
        [{"code": r.reason_code, "passed": r.passed, "evidence": r.evidence} for r in results],
        sort_keys=True,
    )
    evidence_hash = hashlib.sha256(evidence_data.encode()).hexdigest()

    return PolicyVerdict(
        passed=len(failed) == 0,
        results=results,
        failed_codes=failed_codes,
        evidence_hash=evidence_hash,
    )
