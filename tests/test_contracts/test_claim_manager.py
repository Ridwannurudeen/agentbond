"""Tests for ClaimManager.sol using an in-process EVM (py-evm)."""

import json
from pathlib import Path

import pytest
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3, EthereumTesterProvider

ARTIFACTS = Path(__file__).parent.parent.parent / "contracts" / "artifacts" / "src"

ONE_ETH = 10 ** 18
CLAIM_AMOUNT = ONE_ETH // 100  # DEFAULT_CLAIM_AMOUNT = 0.01 ether


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
def full_stack(evm):
    """Deploy AgentRegistry + WarrantyPool + ClaimManager, wire together.

    accounts[0] = owner / resolver
    accounts[1] = agent operator
    accounts[2] = claimant
    """
    w3, accounts = evm
    ar_art = load_artifact("AgentRegistry")
    wp_art = load_artifact("WarrantyPool")
    cm_art = load_artifact("ClaimManager")

    # AgentRegistry (resolver = accounts[0])
    ar_f = w3.eth.contract(abi=ar_art["abi"], bytecode=ar_art["bytecode"])
    tx = ar_f.constructor(accounts[0]).transact({"from": accounts[0]})
    ar_addr = w3.eth.get_transaction_receipt(tx)["contractAddress"]
    reg = w3.eth.contract(address=ar_addr, abi=ar_art["abi"])

    # WarrantyPool
    wp_f = w3.eth.contract(abi=wp_art["abi"], bytecode=wp_art["bytecode"])
    tx = wp_f.constructor(ar_addr).transact({"from": accounts[0]})
    wp_addr = w3.eth.get_transaction_receipt(tx)["contractAddress"]
    pool = w3.eth.contract(address=wp_addr, abi=wp_art["abi"])

    # ClaimManager (resolver = accounts[0])
    cm_f = w3.eth.contract(abi=cm_art["abi"], bytecode=cm_art["bytecode"])
    tx = cm_f.constructor(wp_addr, accounts[0]).transact({"from": accounts[0]})
    cm_addr = w3.eth.get_transaction_receipt(tx)["contractAddress"]
    cm = w3.eth.contract(address=cm_addr, abi=cm_art["abi"])

    # Wire WarrantyPool → ClaimManager
    pool.functions.setClaimManager(cm_addr).transact({"from": accounts[0]})

    return w3, accounts, reg, pool, cm


@pytest.fixture()
def staked_agent(full_stack):
    """Register agent, stake 1 ETH. Returns (..., agent_id)."""
    w3, accounts, reg, pool, cm = full_stack
    tx = reg.functions.registerAgent("ipfs://QmClaim").transact({"from": accounts[1]})
    logs = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    agent_id = logs[0]["args"]["agentId"]
    pool.functions.stake(agent_id).transact({"from": accounts[1], "value": ONE_ETH})
    return w3, accounts, reg, pool, cm, agent_id


@pytest.fixture()
def submitted_claim(staked_agent):
    """Submit one claim and return (..., agent_id, claim_id, run_id)."""
    w3, accounts, reg, pool, cm, agent_id = staked_agent
    run_id = Web3.keccak(text="run-001")
    evidence = Web3.keccak(text="evidence-001")
    tx = cm.functions.submitClaim(run_id, agent_id, "POLICY_VIOLATION", evidence).transact(
        {"from": accounts[2]}
    )
    logs = cm.events.ClaimSubmitted().process_receipt(w3.eth.get_transaction_receipt(tx))
    claim_id = logs[0]["args"]["claimId"]
    return w3, accounts, reg, pool, cm, agent_id, claim_id, run_id


# ---------------------------------------------------------------------------
# submitClaim
# ---------------------------------------------------------------------------

def test_submit_claim_emits_event(staked_agent):
    w3, accounts, reg, pool, cm, agent_id = staked_agent
    run_id = Web3.keccak(text="run-submit")
    evidence = Web3.keccak(text="ev-submit")
    tx = cm.functions.submitClaim(run_id, agent_id, "VIOLATION", evidence).transact(
        {"from": accounts[2]}
    )
    logs = cm.events.ClaimSubmitted().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["claimant"] == accounts[2]
    assert logs[0]["args"]["runId"] == run_id


def test_submit_claim_increments_id(staked_agent):
    w3, accounts, reg, pool, cm, agent_id = staked_agent
    before = cm.functions.nextClaimId().call()
    run_id = Web3.keccak(text="run-incr")
    cm.functions.submitClaim(run_id, agent_id, "V", Web3.keccak(text="e")).transact(
        {"from": accounts[2]}
    )
    assert cm.functions.nextClaimId().call() == before + 1


def test_submit_claim_stores_correctly(staked_agent):
    w3, accounts, reg, pool, cm, agent_id = staked_agent
    run_id = Web3.keccak(text="run-store")
    evidence = Web3.keccak(text="ev-store")
    tx = cm.functions.submitClaim(run_id, agent_id, "REASON", evidence).transact(
        {"from": accounts[2]}
    )
    logs = cm.events.ClaimSubmitted().process_receipt(w3.eth.get_transaction_receipt(tx))
    claim_id = logs[0]["args"]["claimId"]
    claim = cm.functions.getClaim(claim_id).call()
    assert claim[0] == run_id          # runId
    assert claim[1] == accounts[2]     # claimant
    assert claim[2] == agent_id        # agentId
    assert claim[3] == "REASON"        # reasonCode
    assert claim[4] == evidence        # evidenceHash
    assert claim[5] == 0               # Submitted
    assert claim[6] == CLAIM_AMOUNT    # amount


def test_duplicate_run_claim_rejected(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    evidence2 = Web3.keccak(text="ev2")
    with pytest.raises(Exception, match="Claim already exists for this run"):
        cm.functions.submitClaim(run_id, agent_id, "REPEAT", evidence2).transact(
            {"from": accounts[3]}
        )


def test_submit_reserves_collateral(staked_agent):
    w3, accounts, reg, pool, cm, agent_id = staked_agent
    run_id = Web3.keccak(text="run-reserve")
    cm.functions.submitClaim(run_id, agent_id, "V", Web3.keccak(text="e")).transact(
        {"from": accounts[2]}
    )
    health = pool.functions.getCollateralHealth(agent_id).call()
    assert health[1] == CLAIM_AMOUNT  # reserved


# ---------------------------------------------------------------------------
# verifyClaim
# ---------------------------------------------------------------------------

def test_verify_claim_resolver_only(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    with pytest.raises(Exception, match="Not resolver"):
        cm.functions.verifyClaim(claim_id, True).transact({"from": accounts[3]})


def test_verify_claim_rejected_releases_collateral(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    cm.functions.verifyClaim(claim_id, False).transact({"from": accounts[0]})
    claim = cm.functions.getClaim(claim_id).call()
    assert claim[5] == 3  # Rejected
    # Reserved collateral should be released
    health = pool.functions.getCollateralHealth(agent_id).call()
    assert health[1] == 0


def test_verify_claim_approved_sets_status(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    tx = cm.functions.verifyClaim(claim_id, True).transact({"from": accounts[0]})
    logs = cm.events.ClaimResolved().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert logs[0]["args"]["approved"] is True
    claim = cm.functions.getClaim(claim_id).call()
    assert claim[5] == 2  # Approved


def test_verify_already_verified_rejected(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    cm.functions.verifyClaim(claim_id, True).transact({"from": accounts[0]})
    with pytest.raises(Exception, match="Invalid claim status"):
        cm.functions.verifyClaim(claim_id, True).transact({"from": accounts[0]})


# ---------------------------------------------------------------------------
# executePayout
# ---------------------------------------------------------------------------

def test_execute_payout_resolver_only(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    cm.functions.verifyClaim(claim_id, True).transact({"from": accounts[0]})
    with pytest.raises(Exception, match="Not resolver"):
        cm.functions.executePayout(claim_id).transact({"from": accounts[3]})


def test_execute_payout_requires_approved_status(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    # Claim is still Submitted — not Approved
    with pytest.raises(Exception, match="Claim not approved"):
        cm.functions.executePayout(claim_id).transact({"from": accounts[0]})


def test_execute_payout_full_flow(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    claimant = accounts[2]
    before_balance = w3.eth.get_balance(claimant)

    cm.functions.verifyClaim(claim_id, True).transact({"from": accounts[0]})
    tx = cm.functions.executePayout(claim_id).transact({"from": accounts[0]})

    # Status is Paid
    claim = cm.functions.getClaim(claim_id).call()
    assert claim[5] == 4  # Paid

    # ClaimPaid event emitted
    logs = cm.events.ClaimPaid().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["claimId"] == claim_id
    assert logs[0]["args"]["amount"] == CLAIM_AMOUNT

    # Claimant received ETH (balance increased by at least CLAIM_AMOUNT minus gas)
    after_balance = w3.eth.get_balance(claimant)
    assert after_balance > before_balance


def test_execute_payout_slashes_staked_collateral(submitted_claim):
    w3, accounts, reg, pool, cm, agent_id, claim_id, run_id = submitted_claim
    cm.functions.verifyClaim(claim_id, True).transact({"from": accounts[0]})
    cm.functions.executePayout(claim_id).transact({"from": accounts[0]})

    health = pool.functions.getCollateralHealth(agent_id).call()
    assert health[0] == ONE_ETH - CLAIM_AMOUNT  # staked reduced by payout


# ---------------------------------------------------------------------------
# rate limiting
# ---------------------------------------------------------------------------

def test_daily_claim_limit(staked_agent):
    w3, accounts, reg, pool, cm, agent_id = staked_agent
    # Add more stake so we don't run out
    pool.functions.stake(agent_id).transact({"from": accounts[1], "value": ONE_ETH * 10})

    max_claims = cm.functions.MAX_CLAIMS_PER_DAY().call()
    for i in range(max_claims):
        run_id = Web3.keccak(text=f"run-limit-{i}")
        cm.functions.submitClaim(run_id, agent_id, "V", Web3.keccak(text=f"e{i}")).transact(
            {"from": accounts[2]}
        )

    # Next claim should fail
    with pytest.raises(Exception, match="Daily claim limit reached"):
        run_id = Web3.keccak(text="run-limit-over")
        cm.functions.submitClaim(run_id, agent_id, "V", Web3.keccak(text="over")).transact(
            {"from": accounts[2]}
        )
