"""Tests for the policy engine - all 6 rule checks + combined evaluation."""

import time
import pytest
from backend.services.policy_engine import (
    check_tool_whitelist,
    check_value_limits,
    check_prohibited_targets,
    check_action_frequency,
    check_data_freshness,
    check_model_mismatch,
    evaluate_policy,
)


class TestToolWhitelist:
    def test_pass_when_all_tools_allowed(self):
        transcript = [
            {"role": "tool_call", "tool": "get_price", "args": {}},
            {"role": "tool_call", "tool": "get_portfolio", "args": {}},
        ]
        policy = {"allowed_tools": ["get_price", "get_portfolio", "calculate_risk"]}
        result = check_tool_whitelist(transcript, policy)
        assert result.passed is True

    def test_fail_when_tool_not_allowed(self):
        transcript = [
            {"role": "tool_call", "tool": "get_price", "args": {}},
            {"role": "tool_call", "tool": "send_funds", "args": {}},
        ]
        policy = {"allowed_tools": ["get_price"]}
        result = check_tool_whitelist(transcript, policy)
        assert result.passed is False
        assert result.reason_code == "TOOL_WHITELIST_VIOLATION"
        assert "send_funds" in result.evidence["disallowed_tools"]

    def test_pass_when_no_whitelist_defined(self):
        transcript = [{"role": "tool_call", "tool": "anything", "args": {}}]
        policy = {}
        result = check_tool_whitelist(transcript, policy)
        assert result.passed is True

    def test_pass_when_no_tool_calls(self):
        transcript = [{"role": "user", "content": "hello"}]
        policy = {"allowed_tools": ["get_price"]}
        result = check_tool_whitelist(transcript, policy)
        assert result.passed is True


class TestValueLimits:
    def test_pass_within_limit(self):
        transcript = [
            {"role": "tool_call", "tool": "transfer", "args": {"value": 50}},
        ]
        policy = {"max_value_per_action": 100}
        result = check_value_limits(transcript, policy)
        assert result.passed is True

    def test_fail_exceeds_limit(self):
        transcript = [
            {"role": "tool_call", "tool": "transfer", "args": {"value": 150}},
        ]
        policy = {"max_value_per_action": 100}
        result = check_value_limits(transcript, policy)
        assert result.passed is False
        assert result.reason_code == "VALUE_LIMIT_EXCEEDED"

    def test_pass_no_limit_set(self):
        transcript = [
            {"role": "tool_call", "tool": "transfer", "args": {"value": 999999}},
        ]
        policy = {}
        result = check_value_limits(transcript, policy)
        assert result.passed is True

    def test_uses_amount_field(self):
        transcript = [
            {"role": "tool_call", "tool": "transfer", "args": {"amount": 200}},
        ]
        policy = {"max_value_per_action": 100}
        result = check_value_limits(transcript, policy)
        assert result.passed is False


class TestProhibitedTargets:
    def test_pass_no_prohibited_targets(self):
        transcript = [
            {"role": "tool_call", "tool": "send", "args": {"target": "0xabc"}},
        ]
        policy = {"prohibited_targets": []}
        result = check_prohibited_targets(transcript, policy)
        assert result.passed is True

    def test_fail_prohibited_target(self):
        transcript = [
            {"role": "tool_call", "tool": "send", "args": {"target": "0xDEAD"}},
        ]
        policy = {"prohibited_targets": ["0xdead"]}
        result = check_prohibited_targets(transcript, policy)
        assert result.passed is False
        assert result.reason_code == "PROHIBITED_TARGET"

    def test_case_insensitive(self):
        transcript = [
            {"role": "tool_call", "tool": "send", "args": {"to": "0xDeAd"}},
        ]
        policy = {"prohibited_targets": ["0xDEAD"]}
        result = check_prohibited_targets(transcript, policy)
        assert result.passed is False


class TestActionFrequency:
    def test_pass_within_limit(self):
        now = time.time()
        history = [{"timestamp": now - 10} for _ in range(5)]
        policy = {"max_actions_per_window": 10, "window_seconds": 60}
        result = check_action_frequency(history, policy)
        assert result.passed is True

    def test_fail_exceeds_limit(self):
        now = time.time()
        history = [{"timestamp": now - 10} for _ in range(15)]
        policy = {"max_actions_per_window": 10, "window_seconds": 60}
        result = check_action_frequency(history, policy)
        assert result.passed is False
        assert result.reason_code == "FREQUENCY_EXCEEDED"

    def test_old_actions_excluded(self):
        now = time.time()
        history = [{"timestamp": now - 1000} for _ in range(15)]
        policy = {"max_actions_per_window": 10, "window_seconds": 60}
        result = check_action_frequency(history, policy)
        assert result.passed is True


class TestDataFreshness:
    def test_pass_fresh_data(self):
        now = time.time()
        metadata = {"data_sources": [{"name": "price_feed", "timestamp": now - 10}]}
        policy = {"required_data_freshness_seconds": 300}
        result = check_data_freshness(metadata, policy)
        assert result.passed is True

    def test_fail_stale_data(self):
        now = time.time()
        metadata = {"data_sources": [{"name": "price_feed", "timestamp": now - 600}]}
        policy = {"required_data_freshness_seconds": 300}
        result = check_data_freshness(metadata, policy)
        assert result.passed is False
        assert result.reason_code == "STALE_DATA"


class TestModelMismatch:
    def test_pass_matching_models(self):
        metadata = {"declared_model": "llama-3.1-8b", "executed_model": "llama-3.1-8b"}
        result = check_model_mismatch(metadata, {})
        assert result.passed is True

    def test_fail_mismatched_models(self):
        metadata = {"declared_model": "llama-3.1-8b", "executed_model": "gpt-4"}
        result = check_model_mismatch(metadata, {})
        assert result.passed is False
        assert result.reason_code == "MODEL_MISMATCH"

    def test_pass_no_model_info(self):
        result = check_model_mismatch({}, {})
        assert result.passed is True


class TestEvaluatePolicy:
    def test_all_pass(self):
        transcript = [
            {"role": "tool_call", "tool": "get_price", "args": {"value": 10}},
        ]
        policy = {
            "allowed_tools": ["get_price"],
            "max_value_per_action": 100,
            "prohibited_targets": [],
        }
        verdict = evaluate_policy(transcript, policy)
        assert verdict.passed is True
        assert len(verdict.failed_codes) == 0
        assert verdict.evidence_hash

    def test_multiple_violations(self):
        transcript = [
            {"role": "tool_call", "tool": "hack_system", "args": {"value": 9999, "target": "0xdead"}},
        ]
        policy = {
            "allowed_tools": ["get_price"],
            "max_value_per_action": 100,
            "prohibited_targets": ["0xdead"],
        }
        verdict = evaluate_policy(transcript, policy)
        assert verdict.passed is False
        assert "TOOL_WHITELIST_VIOLATION" in verdict.failed_codes
        assert "VALUE_LIMIT_EXCEEDED" in verdict.failed_codes
        assert "PROHIBITED_TARGET" in verdict.failed_codes

    def test_deterministic_evidence_hash(self):
        transcript = [{"role": "tool_call", "tool": "get_price", "args": {}}]
        policy = {"allowed_tools": ["get_price"]}
        v1 = evaluate_policy(transcript, policy)
        v2 = evaluate_policy(transcript, policy)
        assert v1.evidence_hash == v2.evidence_hash
