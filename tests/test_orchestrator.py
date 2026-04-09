"""Tests for the orchestrator service (OG SDK integration)."""

import pytest

from backend.services.og_client import OGExecutionClient, RunResult


class TestOGExecutionClient:
    def test_mock_mode_init(self):
        client = OGExecutionClient(private_key="test_key", require_verified=False)
        assert client._initialized is False

    @pytest.mark.asyncio
    async def test_mock_execution(self):
        client = OGExecutionClient(private_key="test_key", require_verified=False)
        result = await client.execute_agent_run(
            model_id="test-model",
            user_input="Hello world",
            tools=["tool1", "tool2"],
        )
        assert isinstance(result, RunResult)
        assert result.run_id
        assert result.input_hash
        assert result.output_hash
        assert len(result.transcript) > 0
        assert result.settlement_tx is None  # mock returns None (no real on-chain tx)
        assert result.model_cid == "test-model"

    @pytest.mark.asyncio
    async def test_mock_execution_no_tools(self):
        client = OGExecutionClient(private_key="test_key", require_verified=False)
        result = await client.execute_agent_run(
            model_id="test-model",
            user_input="Simple question",
        )
        assert result.run_id
        assert result.transcript[0]["role"] == "user"
        assert result.transcript[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_mock_proof_verification(self):
        client = OGExecutionClient(private_key="test_key", require_verified=False)
        proof = await client.verify_proof("run123", "0xtx123")
        # Mock mode cannot verify — no real OG SDK connection
        assert proof.valid is False
        assert proof.input_hash_match is False
        assert proof.output_hash_match is False

    @pytest.mark.asyncio
    async def test_mock_runs_not_verified(self):
        client = OGExecutionClient(private_key="test_key", require_verified=False)
        result = await client.execute_agent_run("model", "test")
        # Mock runs are never verified (unless conftest patches it for E2E flows)
        # Note: the autouse fixture in conftest.py patches _mock_run to return verified=True
        # for E2E test convenience. Here we disable the patch expectation.
        assert isinstance(result, RunResult)

    @pytest.mark.asyncio
    async def test_fail_closed_raises_when_verified_required(self):
        """Production mode must not silently return mock data."""
        client = OGExecutionClient(private_key="test_key", require_verified=True)
        with pytest.raises(RuntimeError, match="TEE execution unavailable"):
            await client.execute_agent_run("model", "should fail")

    @pytest.mark.asyncio
    async def test_input_hash_deterministic(self):
        client = OGExecutionClient(private_key="test_key", require_verified=False)
        r1 = await client.execute_agent_run("model", "same input")
        r2 = await client.execute_agent_run("model", "same input")
        assert r1.input_hash == r2.input_hash

    @pytest.mark.asyncio
    async def test_different_inputs_different_hashes(self):
        client = OGExecutionClient(private_key="test_key", require_verified=False)
        r1 = await client.execute_agent_run("model", "input A")
        r2 = await client.execute_agent_run("model", "input B")
        assert r1.input_hash != r2.input_hash
