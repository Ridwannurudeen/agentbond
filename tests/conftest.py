"""Shared test configuration and fixtures."""

import pytest
from unittest.mock import patch

# Disable fail-closed mode BEFORE orchestrator imports construct the singleton.
# In production this must be True. Tests run entirely against the mock OG client.
from backend.config import settings as _settings
_settings.require_verified_execution = False

# Also relax the singleton if it was already constructed by an earlier import
try:
    from backend.services.orchestrator import og_client as _og_client
    _og_client.require_verified = False
except Exception:
    pass


TEST_DB_URL = "sqlite+aiosqlite:///test_shared.db"

# Dummy values passed in requests so the presence check passes
TEST_SIGNATURE = "0x" + "a" * 130
TEST_MESSAGE = "test message"


@pytest.fixture(autouse=True)
def mock_verify_wallet_signature():
    """Bypass wallet signature verification in all tests."""
    with patch("backend.auth.verify_wallet_signature", return_value=True), \
         patch("backend.routers.agents.verify_wallet_signature", return_value=True), \
         patch("backend.routers.claims.verify_wallet_signature", return_value=True), \
         patch("backend.routers.runs.verify_wallet_signature", return_value=True), \
         patch("backend.main.verify_wallet_signature", return_value=True):
        yield


@pytest.fixture(autouse=True)
def mark_test_runs_verified():
    """For tests, treat mock runs as verified so claims can be exercised end-to-end.

    Production uses `require_verified_execution=True` so mock data is never served;
    in tests we simulate the TEE path by forcing the RunResult.verified flag to True.
    """
    from backend.services import og_client as _og_module
    original = _og_module.OGExecutionClient._mock_run

    def _patched_mock_run(self, run_id, input_hash, model_id, user_input, tools, simulate_tools):
        result = original(self, run_id, input_hash, model_id, user_input, tools, simulate_tools)
        result.verified = True
        return result

    with patch.object(_og_module.OGExecutionClient, "_mock_run", _patched_mock_run):
        yield
