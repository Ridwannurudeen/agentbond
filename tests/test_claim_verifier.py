"""Tests for claim verification logic."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from backend.services.claim_verifier import verify_claim, VALID_REASON_CODES


@pytest.fixture
def mock_db():
    """Create a mock async session."""
    db = AsyncMock()
    return db


@pytest.fixture
def mock_claim():
    claim = MagicMock()
    claim.id = 1
    claim.run_id = 1
    claim.agent_id = 1
    claim.claimant_address = "0xuser"
    claim.reason_code = "TOOL_WHITELIST_VIOLATION"
    claim.evidence_hash = "abc123"
    claim.status = "submitted"
    return claim


@pytest.fixture
def mock_run():
    run = MagicMock()
    run.id = 1
    run.agent_id = 1
    run.transcript_json = [
        {"role": "tool_call", "tool": "hack_system", "args": {}},
    ]
    return run


@pytest.fixture
def mock_policy():
    policy = MagicMock()
    policy.rules_json = {
        "allowed_tools": ["get_price"],
    }
    return policy


class TestValidReasonCodes:
    def test_all_codes_present(self):
        expected = {
            "TOOL_WHITELIST_VIOLATION",
            "VALUE_LIMIT_EXCEEDED",
            "PROHIBITED_TARGET",
            "FREQUENCY_EXCEEDED",
            "STALE_DATA",
            "MODEL_MISMATCH",
        }
        assert VALID_REASON_CODES == expected


class TestVerifyClaim:
    @pytest.mark.asyncio
    async def test_claim_not_found(self, mock_db):
        mock_db.get.return_value = None
        result = await verify_claim(mock_db, 999)
        assert result.valid is False
        assert "not found" in result.reason

    @pytest.mark.asyncio
    async def test_invalid_status(self, mock_db, mock_claim):
        mock_claim.status = "approved"
        mock_db.get.return_value = mock_claim
        result = await verify_claim(mock_db, 1)
        assert result.valid is False
        assert "Invalid claim status" in result.reason

    @pytest.mark.asyncio
    async def test_invalid_reason_code(self, mock_db, mock_claim):
        mock_claim.reason_code = "INVALID_CODE"
        mock_db.get.return_value = mock_claim
        result = await verify_claim(mock_db, 1)
        assert result.valid is True
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_approved_when_violation_confirmed(self, mock_db, mock_claim, mock_run, mock_policy):
        # First call returns claim, second returns run
        mock_db.get.side_effect = [mock_claim, mock_run]

        # Mock the policy query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_policy
        mock_db.execute.return_value = mock_result

        result = await verify_claim(mock_db, 1)
        assert result.valid is True
        assert result.approved is True
        assert "confirmed" in result.reason

    @pytest.mark.asyncio
    async def test_rejected_when_no_violation(self, mock_db, mock_claim, mock_policy):
        # Clean transcript - no violations
        mock_run = MagicMock()
        mock_run.transcript_json = [
            {"role": "tool_call", "tool": "get_price", "args": {}},
        ]

        mock_db.get.side_effect = [mock_claim, mock_run]

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_policy
        mock_db.execute.return_value = mock_result

        result = await verify_claim(mock_db, 1)
        assert result.valid is True
        assert result.approved is False
        assert "not found" in result.reason
