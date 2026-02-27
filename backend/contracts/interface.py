"""Contract interaction layer for AgentBond smart contracts."""

import json
import logging
from pathlib import Path
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from backend.config import settings

logger = logging.getLogger(__name__)

# ABI definitions (simplified for key methods)
AGENT_REGISTRY_ABI = json.loads("""[
    {"inputs":[{"name":"metadataURI","type":"string"}],"name":"registerAgent","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"},{"name":"versionHash","type":"bytes32"},{"name":"policyId","type":"uint256"}],"name":"publishVersion","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"},{"name":"status","type":"uint8"}],"name":"setStatus","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"},{"name":"newScore","type":"uint256"},{"name":"totalRuns","type":"uint256"},{"name":"violationCount","type":"uint256"}],"name":"updateScore","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getAgent","outputs":[{"components":[{"name":"operator","type":"address"},{"name":"metadataURI","type":"string"},{"name":"activeVersion","type":"uint256"},{"name":"status","type":"uint8"},{"name":"trustScore","type":"uint256"},{"name":"totalRuns","type":"uint256"},{"name":"violations","type":"uint256"},{"name":"createdAt","type":"uint256"}],"name":"","type":"tuple"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getScore","outputs":[{"name":"","type":"uint256"},{"name":"","type":"uint256"},{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"agentId","type":"uint256"},{"indexed":true,"name":"operator","type":"address"}],"name":"AgentRegistered","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"agentId","type":"uint256"},{"indexed":true,"name":"versionId","type":"uint256"}],"name":"VersionPublished","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"agentId","type":"uint256"},{"name":"newScore","type":"uint256"}],"name":"ScoreUpdated","type":"event"}
]""")

POLICY_REGISTRY_ABI = json.loads("""[
    {"inputs":[{"name":"agentId","type":"uint256"},{"name":"policyHash","type":"bytes32"},{"name":"rulesURI","type":"string"}],"name":"registerPolicy","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"},{"name":"policyId","type":"uint256"}],"name":"activatePolicy","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"policyId","type":"uint256"}],"name":"getPolicy","outputs":[{"components":[{"name":"agentId","type":"uint256"},{"name":"policyHash","type":"bytes32"},{"name":"rulesURI","type":"string"},{"name":"status","type":"uint8"},{"name":"createdAt","type":"uint256"}],"name":"","type":"tuple"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getActivePolicy","outputs":[{"name":"","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"policyId","type":"uint256"},{"indexed":true,"name":"agentId","type":"uint256"}],"name":"PolicyRegistered","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"agentId","type":"uint256"},{"indexed":true,"name":"policyId","type":"uint256"}],"name":"PolicyActivated","type":"event"}
]""")

WARRANTY_POOL_ABI = json.loads("""[
    {"inputs":[{"name":"agentId","type":"uint256"}],"name":"stake","outputs":[],"stateMutability":"payable","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"},{"name":"amount","type":"uint256"}],"name":"requestUnstake","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"requestId","type":"uint256"}],"name":"finalizeUnstake","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"agentId","type":"uint256"}],"name":"getCollateralHealth","outputs":[{"name":"staked","type":"uint256"},{"name":"reserved","type":"uint256"},{"name":"free","type":"uint256"},{"name":"ratioBps","type":"uint256"}],"stateMutability":"view","type":"function"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"agentId","type":"uint256"},{"name":"amount","type":"uint256"}],"name":"Staked","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"agentId","type":"uint256"},{"name":"amount","type":"uint256"},{"indexed":true,"name":"requestId","type":"uint256"}],"name":"UnstakeRequested","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"agentId","type":"uint256"},{"name":"amount","type":"uint256"},{"indexed":true,"name":"claimId","type":"uint256"}],"name":"SlashExecuted","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"recipient","type":"address"},{"name":"amount","type":"uint256"},{"indexed":true,"name":"claimId","type":"uint256"}],"name":"PayoutSent","type":"event"}
]""")

CLAIM_MANAGER_ABI = json.loads("""[
    {"inputs":[{"name":"runId","type":"bytes32"},{"name":"agentId","type":"uint256"},{"name":"reasonCode","type":"string"},{"name":"evidenceHash","type":"bytes32"}],"name":"submitClaim","outputs":[{"name":"","type":"uint256"}],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"claimId","type":"uint256"},{"name":"approved","type":"bool"}],"name":"verifyClaim","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"claimId","type":"uint256"}],"name":"executePayout","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"name":"claimId","type":"uint256"}],"name":"getClaim","outputs":[{"components":[{"name":"runId","type":"bytes32"},{"name":"claimant","type":"address"},{"name":"agentId","type":"uint256"},{"name":"reasonCode","type":"string"},{"name":"evidenceHash","type":"bytes32"},{"name":"status","type":"uint8"},{"name":"amount","type":"uint256"},{"name":"createdAt","type":"uint256"},{"name":"resolvedAt","type":"uint256"}],"name":"","type":"tuple"}],"stateMutability":"view","type":"function"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"claimId","type":"uint256"},{"indexed":true,"name":"runId","type":"bytes32"},{"indexed":true,"name":"claimant","type":"address"}],"name":"ClaimSubmitted","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"claimId","type":"uint256"},{"name":"approved","type":"bool"}],"name":"ClaimResolved","type":"event"},
    {"anonymous":false,"inputs":[{"indexed":true,"name":"claimId","type":"uint256"},{"name":"amount","type":"uint256"}],"name":"ClaimPaid","type":"event"}
]""")


class ContractInterface:
    """Unified interface for interacting with AgentBond contracts."""

    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(settings.og_rpc_url))
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

        self._account = None
        if settings.og_private_key:
            self._account = self.w3.eth.account.from_key(settings.og_private_key)

        self.agent_registry = self._get_contract(
            settings.agent_registry_address, AGENT_REGISTRY_ABI
        ) if settings.agent_registry_address else None

        self.policy_registry = self._get_contract(
            settings.policy_registry_address, POLICY_REGISTRY_ABI
        ) if settings.policy_registry_address else None

        self.warranty_pool = self._get_contract(
            settings.warranty_pool_address, WARRANTY_POOL_ABI
        ) if settings.warranty_pool_address else None

        self.claim_manager = self._get_contract(
            settings.claim_manager_address, CLAIM_MANAGER_ABI
        ) if settings.claim_manager_address else None

    def is_configured(self) -> bool:
        """Returns True if the private key and all contract addresses are set."""
        return (
            self._account is not None
            and self.agent_registry is not None
            and self.policy_registry is not None
            and self.warranty_pool is not None
            and self.claim_manager is not None
        )

    def _get_contract(self, address: str, abi: list):
        if not address:
            return None
        return self.w3.eth.contract(
            address=Web3.to_checksum_address(address), abi=abi
        )

    def _send_tx(self, func, value=0):
        """Build, sign, and send a transaction."""
        if not self._account:
            raise RuntimeError("No private key configured")

        tx = func.build_transaction({
            "from": self._account.address,
            "nonce": self.w3.eth.get_transaction_count(self._account.address),
            "gas": 500_000,
            "gasPrice": self.w3.eth.gas_price,
            "chainId": settings.chain_id,
            "value": value,
        })
        signed = self._account.sign_transaction(tx)
        tx_hash = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
        logger.info(f"TX confirmed: {tx_hash.hex()} (block {receipt.blockNumber})")
        return receipt

    # --- Agent Registry ---

    def register_agent(self, metadata_uri: str) -> tuple[int, str]:
        func = self.agent_registry.functions.registerAgent(metadata_uri)
        receipt = self._send_tx(func)
        logs = self.agent_registry.events.AgentRegistered().process_receipt(receipt)
        agent_id = logs[0]["args"]["agentId"]
        return agent_id, receipt.transactionHash.hex()

    def publish_version(self, agent_id: int, version_hash: bytes, policy_id: int) -> tuple[int, str]:
        func = self.agent_registry.functions.publishVersion(agent_id, version_hash, policy_id)
        receipt = self._send_tx(func)
        logs = self.agent_registry.events.VersionPublished().process_receipt(receipt)
        version_id = logs[0]["args"]["versionId"]
        return version_id, receipt.transactionHash.hex()

    def get_agent(self, agent_id: int) -> dict:
        result = self.agent_registry.functions.getAgent(agent_id).call()
        return {
            "operator": result[0],
            "metadataURI": result[1],
            "activeVersion": result[2],
            "status": result[3],
            "trustScore": result[4],
            "totalRuns": result[5],
            "violations": result[6],
            "createdAt": result[7],
        }

    def get_score(self, agent_id: int) -> dict:
        score, runs, violations = self.agent_registry.functions.getScore(agent_id).call()
        return {"trustScore": score, "totalRuns": runs, "violations": violations}

    def update_score(self, agent_id: int, score: int, total_runs: int, violations: int) -> str:
        func = self.agent_registry.functions.updateScore(agent_id, score, total_runs, violations)
        receipt = self._send_tx(func)
        return receipt.transactionHash.hex()

    # --- Policy Registry ---

    def register_policy(self, agent_id: int, policy_hash: bytes, rules_uri: str) -> tuple[int, str]:
        func = self.policy_registry.functions.registerPolicy(agent_id, policy_hash, rules_uri)
        receipt = self._send_tx(func)
        logs = self.policy_registry.events.PolicyRegistered().process_receipt(receipt)
        policy_id = logs[0]["args"]["policyId"]
        return policy_id, receipt.transactionHash.hex()

    def activate_policy(self, agent_id: int, policy_id: int) -> str:
        func = self.policy_registry.functions.activatePolicy(agent_id, policy_id)
        receipt = self._send_tx(func)
        return receipt.transactionHash.hex()

    # --- Warranty Pool ---

    def stake(self, agent_id: int, amount_wei: int) -> str:
        func = self.warranty_pool.functions.stake(agent_id)
        receipt = self._send_tx(func, value=amount_wei)
        return receipt.transactionHash.hex()

    def request_unstake(self, agent_id: int, amount_wei: int) -> tuple[int, str]:
        func = self.warranty_pool.functions.requestUnstake(agent_id, amount_wei)
        receipt = self._send_tx(func)
        logs = self.warranty_pool.events.UnstakeRequested().process_receipt(receipt)
        request_id = logs[0]["args"]["requestId"] if logs else 0
        return request_id, receipt.transactionHash.hex()

    def get_collateral_health(self, agent_id: int) -> dict:
        result = self.warranty_pool.functions.getCollateralHealth(agent_id).call()
        return {
            "staked": result[0],
            "reserved": result[1],
            "free": result[2],
            "ratioBps": result[3],
        }

    # --- Claim Manager ---

    def submit_claim(self, run_id: bytes, agent_id: int, reason_code: str, evidence_hash: bytes) -> tuple[int, str]:
        func = self.claim_manager.functions.submitClaim(run_id, agent_id, reason_code, evidence_hash)
        receipt = self._send_tx(func)
        logs = self.claim_manager.events.ClaimSubmitted().process_receipt(receipt)
        claim_id = logs[0]["args"]["claimId"]
        return claim_id, receipt.transactionHash.hex()

    def verify_claim(self, claim_id: int, approved: bool) -> str:
        func = self.claim_manager.functions.verifyClaim(claim_id, approved)
        receipt = self._send_tx(func)
        return receipt.transactionHash.hex()

    def execute_payout(self, claim_id: int) -> str:
        func = self.claim_manager.functions.executePayout(claim_id)
        receipt = self._send_tx(func)
        return receipt.transactionHash.hex()

    def get_claim(self, claim_id: int) -> dict:
        result = self.claim_manager.functions.getClaim(claim_id).call()
        return {
            "runId": result[0].hex(),
            "claimant": result[1],
            "agentId": result[2],
            "reasonCode": result[3],
            "evidenceHash": result[4].hex(),
            "status": result[5],
            "amount": result[6],
            "createdAt": result[7],
            "resolvedAt": result[8],
        }


# Singleton
contracts = ContractInterface()
