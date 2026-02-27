"""Tests for WarrantyPool.sol using an in-process EVM (py-evm)."""

import json
from pathlib import Path

import pytest
from eth_tester import EthereumTester, PyEVMBackend
from web3 import Web3, EthereumTesterProvider

ARTIFACTS = Path(__file__).parent.parent.parent / "contracts" / "artifacts" / "src"

ONE_ETH = 10 ** 18
HALF_ETH = ONE_ETH // 2


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
    """Deploy AgentRegistry + WarrantyPool."""
    w3, accounts = evm
    ar_art = load_artifact("AgentRegistry")
    wp_art = load_artifact("WarrantyPool")

    ar_factory = w3.eth.contract(abi=ar_art["abi"], bytecode=ar_art["bytecode"])
    tx = ar_factory.constructor(accounts[0]).transact({"from": accounts[0]})
    ar_addr = w3.eth.get_transaction_receipt(tx)["contractAddress"]
    reg = w3.eth.contract(address=ar_addr, abi=ar_art["abi"])

    wp_factory = w3.eth.contract(abi=wp_art["abi"], bytecode=wp_art["bytecode"])
    tx = wp_factory.constructor(ar_addr).transact({"from": accounts[0]})
    wp_addr = w3.eth.get_transaction_receipt(tx)["contractAddress"]
    pool = w3.eth.contract(address=wp_addr, abi=wp_art["abi"])

    return w3, accounts, reg, pool


@pytest.fixture()
def agent(contracts):
    """Register agent and return (w3, accounts, reg, pool, agent_id)."""
    w3, accounts, reg, pool = contracts
    tx = reg.functions.registerAgent("ipfs://QmPool").transact({"from": accounts[1]})
    logs = reg.events.AgentRegistered().process_receipt(w3.eth.get_transaction_receipt(tx))
    return w3, accounts, reg, pool, logs[0]["args"]["agentId"]


@pytest.fixture()
def staked_agent(agent):
    """Agent with 1 ETH staked. Returns (w3, accounts, reg, pool, agent_id)."""
    w3, accounts, reg, pool, agent_id = agent
    pool.functions.stake(agent_id).transact({"from": accounts[1], "value": ONE_ETH})
    return w3, accounts, reg, pool, agent_id


# ---------------------------------------------------------------------------
# stake
# ---------------------------------------------------------------------------

def test_stake_requires_value(agent):
    w3, accounts, reg, pool, agent_id = agent
    with pytest.raises(Exception, match="Must stake > 0"):
        pool.functions.stake(agent_id).transact({"from": accounts[1], "value": 0})


def test_stake_operator_only(agent):
    w3, accounts, reg, pool, agent_id = agent
    with pytest.raises(Exception, match="Not agent operator"):
        pool.functions.stake(agent_id).transact({"from": accounts[3], "value": ONE_ETH})


def test_stake_emits_event(agent):
    w3, accounts, reg, pool, agent_id = agent
    tx = pool.functions.stake(agent_id).transact({"from": accounts[1], "value": ONE_ETH})
    logs = pool.events.Staked().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["agentId"] == agent_id
    assert logs[0]["args"]["amount"] == ONE_ETH


def test_stake_accumulates(agent):
    w3, accounts, reg, pool, agent_id = agent
    pool.functions.stake(agent_id).transact({"from": accounts[1], "value": ONE_ETH})
    pool.functions.stake(agent_id).transact({"from": accounts[1], "value": HALF_ETH})
    health = pool.functions.getCollateralHealth(agent_id).call()
    assert health[0] == ONE_ETH + HALF_ETH  # staked


# ---------------------------------------------------------------------------
# requestUnstake
# ---------------------------------------------------------------------------

def test_request_unstake_operator_only(staked_agent):
    w3, accounts, reg, pool, agent_id = staked_agent
    with pytest.raises(Exception, match="Not agent operator"):
        pool.functions.requestUnstake(agent_id, HALF_ETH).transact({"from": accounts[3]})


def test_request_unstake_exceeds_free(agent):
    w3, accounts, reg, pool, agent_id = agent
    with pytest.raises(Exception, match="Insufficient free collateral"):
        pool.functions.requestUnstake(agent_id, HALF_ETH).transact({"from": accounts[1]})


def test_request_unstake_emits_event(staked_agent):
    w3, accounts, reg, pool, agent_id = staked_agent
    tx = pool.functions.requestUnstake(agent_id, HALF_ETH).transact({"from": accounts[1]})
    logs = pool.events.UnstakeRequested().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["agentId"] == agent_id
    assert logs[0]["args"]["amount"] == HALF_ETH


def test_request_unstake_reduces_staked(staked_agent):
    w3, accounts, reg, pool, agent_id = staked_agent
    pool.functions.requestUnstake(agent_id, HALF_ETH).transact({"from": accounts[1]})
    health = pool.functions.getCollateralHealth(agent_id).call()
    assert health[0] == HALF_ETH  # remaining staked


# ---------------------------------------------------------------------------
# setClaimManager + slash/payout (onlyClaimManager)
# ---------------------------------------------------------------------------

def test_set_claim_manager_owner_only(contracts):
    w3, accounts, reg, pool = contracts
    with pytest.raises(Exception):
        pool.functions.setClaimManager(accounts[5]).transact({"from": accounts[3]})


def test_slash_only_claim_manager(staked_agent):
    w3, accounts, reg, pool, agent_id = staked_agent
    with pytest.raises(Exception, match="Not claim manager"):
        pool.functions.slash(agent_id, HALF_ETH, 1).transact({"from": accounts[0]})


def test_payout_only_claim_manager(staked_agent):
    w3, accounts, reg, pool, agent_id = staked_agent
    with pytest.raises(Exception, match="Not claim manager"):
        pool.functions.payout(accounts[2], HALF_ETH, 1).transact({"from": accounts[0]})


def test_reserve_and_release_collateral(staked_agent):
    w3, accounts, reg, pool, agent_id = staked_agent
    # Designate accounts[0] as claimManager for this test
    pool.functions.setClaimManager(accounts[0]).transact({"from": accounts[0]})

    pool.functions.reserveCollateral(agent_id, HALF_ETH).transact({"from": accounts[0]})
    health = pool.functions.getCollateralHealth(agent_id).call()
    assert health[1] == HALF_ETH  # reserved
    assert health[2] == HALF_ETH  # free

    pool.functions.releaseCollateral(agent_id, HALF_ETH).transact({"from": accounts[0]})
    health = pool.functions.getCollateralHealth(agent_id).call()
    assert health[1] == 0  # released


def test_slash_reduces_stake_and_emits(staked_agent):
    w3, accounts, reg, pool, agent_id = staked_agent
    pool.functions.setClaimManager(accounts[0]).transact({"from": accounts[0]})

    tx = pool.functions.slash(agent_id, HALF_ETH, 42).transact({"from": accounts[0]})
    logs = pool.events.SlashExecuted().process_receipt(w3.eth.get_transaction_receipt(tx))
    assert len(logs) == 1
    assert logs[0]["args"]["agentId"] == agent_id
    assert logs[0]["args"]["amount"] == HALF_ETH

    health = pool.functions.getCollateralHealth(agent_id).call()
    assert health[0] == HALF_ETH  # staked halved


def test_slash_to_zero_reverts(staked_agent):
    """When stake hits zero, WarrantyPool calls AgentRegistry.pauseAgent(), which
    reverts because the pool contract is not the resolver or the operator.
    This is a known design constraint of the deployed contracts — the pool
    address must be added as an authorized pauser to enable auto-pause."""
    w3, accounts, reg, pool, agent_id = staked_agent
    pool.functions.setClaimManager(accounts[0]).transact({"from": accounts[0]})

    with pytest.raises(Exception, match="Not authorized"):
        pool.functions.slash(agent_id, ONE_ETH, 99).transact({"from": accounts[0]})


def test_get_collateral_health_ratio(staked_agent):
    w3, accounts, reg, pool, agent_id = staked_agent
    pool.functions.setClaimManager(accounts[0]).transact({"from": accounts[0]})

    # Reserve 0.01 ETH, staked 1 ETH → ratio = (1e18 * 10000) / 0.01e18 = 1_000_000 bps
    reserve_amt = ONE_ETH // 100
    pool.functions.reserveCollateral(agent_id, reserve_amt).transact({"from": accounts[0]})
    health = pool.functions.getCollateralHealth(agent_id).call()
    expected_ratio = (ONE_ETH * 10000) // reserve_amt
    assert health[3] == expected_ratio
