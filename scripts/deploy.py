"""Deploy AgentBond contracts to OpenGradient testnet."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware
from solcx import compile_standard, install_solc

load_dotenv()

RPC_URL = os.getenv("OG_RPC_URL", "https://testnet-rpc.opengradient.ai")
CHAIN_ID = int(os.getenv("CHAIN_ID", "131072"))
PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY", "")
RESOLVER_ADDRESS = os.getenv("RESOLVER_ADDRESS", "")

CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"


def get_w3():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


def deploy_contract(w3, account, abi, bytecode, *constructor_args):
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = contract.constructor(*constructor_args).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 3_000_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": CHAIN_ID,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"  Deployed at: {receipt.contractAddress} (tx: {tx_hash.hex()})")
    return receipt.contractAddress


def main():
    if not PRIVATE_KEY:
        print("Error: DEPLOYER_PRIVATE_KEY not set in .env")
        sys.exit(1)

    if not RESOLVER_ADDRESS:
        print("Error: RESOLVER_ADDRESS not set in .env")
        sys.exit(1)

    w3 = get_w3()
    account = w3.eth.account.from_key(PRIVATE_KEY)
    balance = w3.eth.get_balance(account.address)
    print(f"Deployer: {account.address}")
    print(f"Balance: {w3.from_wei(balance, 'ether')} OPG")
    print()

    # Note: This assumes contracts have been compiled via Hardhat
    # and ABIs are available in contracts/artifacts/
    artifacts_dir = CONTRACTS_DIR / "artifacts" / "src"

    contracts_to_deploy = [
        ("AgentRegistry", [RESOLVER_ADDRESS]),
        ("PolicyRegistry", [None]),  # placeholder, needs AgentRegistry address
        ("WarrantyPool", [None]),    # placeholder, needs AgentRegistry address
        ("ClaimManager", [None, RESOLVER_ADDRESS]),  # needs WarrantyPool address
    ]

    deployed = {}

    # Deploy AgentRegistry
    print("Deploying AgentRegistry...")
    ar_artifact = artifacts_dir / "AgentRegistry.sol" / "AgentRegistry.json"
    if ar_artifact.exists():
        with open(ar_artifact) as f:
            artifact = json.load(f)
        deployed["AgentRegistry"] = deploy_contract(
            w3, account, artifact["abi"], artifact["bytecode"], RESOLVER_ADDRESS
        )
    else:
        print(f"  Artifact not found at {ar_artifact}")
        print("  Run 'cd contracts && npx hardhat compile' first")
        sys.exit(1)

    # Deploy PolicyRegistry
    print("Deploying PolicyRegistry...")
    pr_artifact = artifacts_dir / "PolicyRegistry.sol" / "PolicyRegistry.json"
    with open(pr_artifact) as f:
        artifact = json.load(f)
    deployed["PolicyRegistry"] = deploy_contract(
        w3, account, artifact["abi"], artifact["bytecode"], deployed["AgentRegistry"]
    )

    # Deploy WarrantyPool
    print("Deploying WarrantyPool...")
    wp_artifact = artifacts_dir / "WarrantyPool.sol" / "WarrantyPool.json"
    with open(wp_artifact) as f:
        artifact = json.load(f)
    deployed["WarrantyPool"] = deploy_contract(
        w3, account, artifact["abi"], artifact["bytecode"], deployed["AgentRegistry"]
    )

    # Deploy ClaimManager
    print("Deploying ClaimManager...")
    cm_artifact = artifacts_dir / "ClaimManager.sol" / "ClaimManager.json"
    with open(cm_artifact) as f:
        artifact = json.load(f)
    deployed["ClaimManager"] = deploy_contract(
        w3, account, artifact["abi"], artifact["bytecode"],
        deployed["WarrantyPool"], RESOLVER_ADDRESS
    )

    # Set ClaimManager on WarrantyPool
    print("\nConfiguring WarrantyPool.setClaimManager...")
    wp_contract = w3.eth.contract(
        address=deployed["WarrantyPool"],
        abi=json.load(open(wp_artifact))["abi"]
    )
    tx = wp_contract.functions.setClaimManager(deployed["ClaimManager"]).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": CHAIN_ID,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    print("  Done")

    print("\n--- Deployment Complete ---")
    print(f"AGENT_REGISTRY_ADDRESS={deployed['AgentRegistry']}")
    print(f"POLICY_REGISTRY_ADDRESS={deployed['PolicyRegistry']}")
    print(f"WARRANTY_POOL_ADDRESS={deployed['WarrantyPool']}")
    print(f"CLAIM_MANAGER_ADDRESS={deployed['ClaimManager']}")
    print("\nAdd these to your .env file.")


if __name__ == "__main__":
    main()
