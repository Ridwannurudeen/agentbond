"""Tests for PolicyRegistry.sol using an in-process EVM (py-evm)."""

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
    tester = EthereumTester(PyEVMBackend())
    w3 = Web3(EthereumTesterProvider(tester))
    return w3, w3.eth.accounts


@pytest.fixture()
def contracts(evm):
    """Deploy AgentRegistry + PolicyRegistry. accounts[0] is resolver/owner."""
    w3, accounts = evm
    ar_art = load_artifact("AgentRegistry")
    pr_art = load_artifact("PolicyRegistry")

    # Deploy AgentRegistry
    ar_factory = w3.eth.contract(abi=ar_art["abi"], bytecode=ar_art["bytecode"])
    tx = ar_factory.constructor(accounts[0]).transact({"from": accounts[0]})
    ar_addr = w3.eth.get_transaction_receipt(tx)["contractAddress"]
    reg = w3.eth.contract(address=ar_addr, abi=ar_art["abi"])

    # Deploy PolicyRegistry
    pr_factory = w3.eth.contract(abi=pr_art["abi"], bytecode=pr_art["bytecode"])
    tx = pr_factory.constructor(ar_addr).transact({"from": accounts[0]})
    pr_addr = w3.eth.get_transaction_receipt(tx)["contractAddress"]
    pol = w3.eth.contract(address=pr_addr, abi=pr_art["abi"])

    return w3, accounts, reg, pol


@pytest.fixture()
def agent(contracts):
    """Register one agent and return (w3, accounts, reg, pol, agent_id)."""
    w3, accounts, reg, pol = contracts
    tx = reg.functions.registerAgent("ipfs://QmAgent").transact({"from": accounts[1]})
    logs = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    agent_id = logs[0]["args"]["agentId"]
    return w3, accounts, reg, pol, agent_id


def _policy_hash(text: str) -> bytes:
    return Web3.keccak(text=text)


# ---------------------------------------------------------------------------
# registerPolicy
# ---------------------------------------------------------------------------

def test_register_policy_operator_only(agent):
    w3, accounts, reg, pol, agent_id = agent
    ph = _policy_hash("rules-v1")
    with pytest.raises(Exception, match="Not agent operator"):
        pol.functions.registerPolicy(agent_id, ph, "uri://rules-v1").transact({"from": accounts[3]})


def test_register_policy_emits_event(agent):
    w3, accounts, reg, pol, agent_id = agent
    ph = _policy_hash("rules-v1")
    tx = pol.functions.registerPolicy(agent_id, ph, "uri://rules-v1").transact({"from": accounts[1]})
    logs = pol.events.PolicyRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["agentId"] == agent_id


def test_register_policy_increments_id(agent):
    w3, accounts, reg, pol, agent_id = agent
    before = pol.functions.nextPolicyId().call()
    pol.functions.registerPolicy(agent_id, _policy_hash("r1"), "u1").transact({"from": accounts[1]})
    assert pol.functions.nextPolicyId().call() == before + 1


def test_registered_policy_stored_correctly(agent):
    w3, accounts, reg, pol, agent_id = agent
    ph = _policy_hash("rules-stored")
    tx = pol.functions.registerPolicy(agent_id, ph, "uri://stored").transact({"from": accounts[1]})
    logs = pol.events.PolicyRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    policy_id = logs[0]["args"]["policyId"]

    stored = pol.functions.getPolicy(policy_id).call()
    assert stored[0] == agent_id          # agentId
    assert stored[1] == ph                # policyHash
    assert stored[2] == "uri://stored"    # rulesURI
    assert stored[3] == 0                 # Active


# ---------------------------------------------------------------------------
# activatePolicy
# ---------------------------------------------------------------------------

@pytest.fixture()
def policy(agent):
    """Register a policy and return (w3, accounts, reg, pol, agent_id, policy_id)."""
    w3, accounts, reg, pol, agent_id = agent
    ph = _policy_hash("rules-activate")
    tx = pol.functions.registerPolicy(agent_id, ph, "uri://activate").transact({"from": accounts[1]})
    logs = pol.events.PolicyRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    policy_id = logs[0]["args"]["policyId"]
    return w3, accounts, reg, pol, agent_id, policy_id


def test_activate_policy_operator_only(policy):
    w3, accounts, reg, pol, agent_id, policy_id = policy
    with pytest.raises(Exception, match="Not agent operator"):
        pol.functions.activatePolicy(agent_id, policy_id).transact({"from": accounts[3]})


def test_activate_policy_emits_event(policy):
    w3, accounts, reg, pol, agent_id, policy_id = policy
    tx = pol.functions.activatePolicy(agent_id, policy_id).transact({"from": accounts[1]})
    logs = pol.events.PolicyActivated().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["agentId"] == agent_id
    assert logs[0]["args"]["policyId"] == policy_id


def test_activate_sets_active_policy(policy):
    w3, accounts, reg, pol, agent_id, policy_id = policy
    pol.functions.activatePolicy(agent_id, policy_id).transact({"from": accounts[1]})
    active = pol.functions.getActivePolicy(agent_id).call()
    assert active == policy_id


def test_activate_wrong_agent_rejected(agent):
    w3, accounts, reg, pol, agent_id = agent

    # Register a second agent
    tx2 = reg.functions.registerAgent("ipfs://QmAgent2").transact({"from": accounts[2]})
    logs2 = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx2))
    agent_id2 = logs2[0]["args"]["agentId"]

    # Register policy for agent1
    ph = _policy_hash("rules-cross")
    tx_p = pol.functions.registerPolicy(agent_id, ph, "u").transact({"from": accounts[1]})
    logs_p = pol.events.PolicyRegistered().process_receipt(w3.eth.get_transaction_receipt(tx_p))
    policy_id = logs_p[0]["args"]["policyId"]

    # Try to activate it for agent2 — should fail with "Policy not for this agent"
    with pytest.raises(Exception, match="Policy not for this agent"):
        pol.functions.activatePolicy(agent_id2, policy_id).transact({"from": accounts[2]})


# ---------------------------------------------------------------------------
# deprecatePolicy
# ---------------------------------------------------------------------------

def test_deprecate_policy_operator_only(policy):
    w3, accounts, reg, pol, agent_id, policy_id = policy
    with pytest.raises(Exception, match="Not agent operator"):
        pol.functions.deprecatePolicy(policy_id).transact({"from": accounts[4]})


def test_deprecate_policy_changes_status(policy):
    w3, accounts, reg, pol, agent_id, policy_id = policy
    pol.functions.deprecatePolicy(policy_id).transact({"from": accounts[1]})
    stored = pol.functions.getPolicy(policy_id).call()
    assert stored[3] == 1  # Deprecated


def test_cannot_activate_deprecated_policy(policy):
    w3, accounts, reg, pol, agent_id, policy_id = policy
    pol.functions.deprecatePolicy(policy_id).transact({"from": accounts[1]})
    with pytest.raises(Exception, match="Policy deprecated"):
        pol.functions.activatePolicy(agent_id, policy_id).transact({"from": accounts[1]})
