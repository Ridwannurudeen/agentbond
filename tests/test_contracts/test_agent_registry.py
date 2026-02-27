"""Tests for AgentRegistry.sol using an in-process EVM (py-evm)."""

import json
from pathlib import Path

import pytest
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3, EthereumTesterProvider

ARTIFACTS = Path(__file__).parent.parent.parent / "contracts" / "artifacts" / "src"


def load_artifact(name: str) -> dict:
    path = ARTIFACTS / f"{name}.sol" / f"{name}.json"
    with open(path) as f:
        return json.load(f)


@pytest.fixture()
def evm():
    """Fresh in-process EVM + funded accounts for each test."""
    tester = EthereumTester(PyEVMBackend())
    w3 = Web3(EthereumTesterProvider(tester))
    accounts = w3.eth.accounts
    return w3, accounts


@pytest.fixture()
def registry(evm):
    """Deploy a fresh AgentRegistry. accounts[0] is both owner and resolver."""
    w3, accounts = evm
    art = load_artifact("AgentRegistry")
    factory = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
    tx = factory.constructor(accounts[0]).transact({"from": accounts[0]})
    receipt = w3.eth.get_transaction_receipt(tx)
    return w3, accounts, w3.eth.contract(address=receipt["contractAddress"], abi=art["abi"])


# ---------------------------------------------------------------------------
# registerAgent
# ---------------------------------------------------------------------------

def test_register_agent_emits_event(registry):
    w3, accounts, reg = registry
    operator = accounts[1]
    tx = reg.functions.registerAgent("ipfs://QmTest").transact({"from": operator})
    logs = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["operator"] == operator


def test_register_agent_increments_id(registry):
    w3, accounts, reg = registry
    before = reg.functions.nextAgentId().call()
    reg.functions.registerAgent("ipfs://QmA").transact({"from": accounts[1]})
    assert reg.functions.nextAgentId().call() == before + 1


def test_registered_agent_defaults(registry):
    w3, accounts, reg = registry
    tx = reg.functions.registerAgent("ipfs://QmDefaults").transact({"from": accounts[1]})
    logs = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    agent_id = logs[0]["args"]["agentId"]
    info = reg.functions.getAgent(agent_id).call()
    assert info[0] == accounts[1]   # operator
    assert info[1] == "ipfs://QmDefaults"  # metadataURI
    assert info[3] == 0             # status Active
    assert info[4] == 100           # trustScore
    assert info[5] == 0             # totalRuns
    assert info[6] == 0             # violations


def test_multiple_agents_get_distinct_ids(registry):
    w3, accounts, reg = registry
    tx1 = reg.functions.registerAgent("ipfs://QmX1").transact({"from": accounts[2]})
    tx2 = reg.functions.registerAgent("ipfs://QmX2").transact({"from": accounts[2]})
    logs1 = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx1))
    logs2 = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx2))
    assert logs1[0]["args"]["agentId"] != logs2[0]["args"]["agentId"]


# ---------------------------------------------------------------------------
# publishVersion
# ---------------------------------------------------------------------------

@pytest.fixture()
def registered_agent(registry):
    """Return (w3, accounts, reg, agent_id) with one agent already registered."""
    w3, accounts, reg = registry
    tx = reg.functions.registerAgent("ipfs://QmAgent").transact({"from": accounts[1]})
    logs = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    return w3, accounts, reg, logs[0]["args"]["agentId"]


def test_publish_version_operator_only(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    version_hash = Web3.keccak(text="v1.0.0")
    with pytest.raises(Exception, match="Not operator"):
        reg.functions.publishVersion(agent_id, version_hash, 0).transact({"from": accounts[3]})


def test_publish_version_emits_event(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    version_hash = Web3.keccak(text="v1.0.1")
    tx = reg.functions.publishVersion(agent_id, version_hash, 0).transact({"from": accounts[1]})
    logs = reg.events.VersionPublished().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["agentId"] == agent_id


def test_publish_version_updates_active_version(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    version_hash = Web3.keccak(text="v1.0.2")
    tx = reg.functions.publishVersion(agent_id, version_hash, 0).transact({"from": accounts[1]})
    logs = reg.events.VersionPublished().process_receipt(w3.eth.get_transaction_receipt(tx))
    version_id = logs[0]["args"]["versionId"]
    info = reg.functions.getAgent(agent_id).call()
    assert info[2] == version_id  # activeVersion


def test_get_version_returns_correct_hash(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    version_hash = Web3.keccak(text="v2.0.0")
    tx = reg.functions.publishVersion(agent_id, version_hash, 0).transact({"from": accounts[1]})
    logs = reg.events.VersionPublished().process_receipt(w3.eth.get_transaction_receipt(tx))
    version_id = logs[0]["args"]["versionId"]
    stored = reg.functions.getVersion(agent_id, version_id).call()
    assert stored[0] == version_hash  # versionHash bytes32


# ---------------------------------------------------------------------------
# updateScore (resolver only)
# ---------------------------------------------------------------------------

def test_update_score_resolver_only(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    with pytest.raises(Exception, match="Not resolver"):
        reg.functions.updateScore(agent_id, 80, 10, 1).transact({"from": accounts[2]})


def test_update_score_changes_values(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    resolver = accounts[0]
    reg.functions.updateScore(agent_id, 75, 20, 3).transact({"from": resolver})
    score, runs, violations = reg.functions.getScore(agent_id).call()
    assert score == 75
    assert runs == 20
    assert violations == 3


def test_update_score_emits_event(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    resolver = accounts[0]
    tx = reg.functions.updateScore(agent_id, 90, 5, 0).transact({"from": resolver})
    logs = reg.events.ScoreUpdated().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["newScore"] == 90


# ---------------------------------------------------------------------------
# pauseAgent
# ---------------------------------------------------------------------------

def test_operator_can_pause_own_agent(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    reg.functions.pauseAgent(agent_id).transact({"from": accounts[1]})
    info = reg.functions.getAgent(agent_id).call()
    assert info[3] == 1  # Paused


def test_resolver_can_pause_agent(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    resolver = accounts[0]
    reg.functions.pauseAgent(agent_id).transact({"from": resolver})
    info = reg.functions.getAgent(agent_id).call()
    assert info[3] == 1  # Paused


def test_random_account_cannot_pause(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    with pytest.raises(Exception, match="Not authorized"):
        reg.functions.pauseAgent(agent_id).transact({"from": accounts[4]})


# ---------------------------------------------------------------------------
# setStatus (operator only)
# ---------------------------------------------------------------------------

def test_set_status_operator_only(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    with pytest.raises(Exception, match="Not operator"):
        reg.functions.setStatus(agent_id, 2).transact({"from": accounts[4]})


def test_set_status_retired(registered_agent):
    w3, accounts, reg, agent_id = registered_agent
    reg.functions.setStatus(agent_id, 2).transact({"from": accounts[1]})  # Retired = 2
    info = reg.functions.getAgent(agent_id).call()
    assert info[3] == 2
