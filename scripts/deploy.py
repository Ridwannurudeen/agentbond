"""Deploy AgentBond contracts to Base Sepolia via UUPS proxies."""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

load_dotenv()

RPC_URL = os.getenv("DEPLOY_RPC_URL", os.getenv("OG_RPC_URL", "https://sepolia.base.org"))
CHAIN_ID = int(os.getenv("DEPLOY_CHAIN_ID", os.getenv("CHAIN_ID", "84532")))
PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY", "")
RESOLVER_ADDRESS = os.getenv("RESOLVER_ADDRESS", "")

CONTRACTS_DIR = Path(__file__).parent.parent / "contracts"

# ERC1967 proxy bytecode (minimal UUPS proxy)
# Uses OpenZeppelin's ERC1967Proxy
PROXY_ARTIFACT = "node_modules/@openzeppelin/contracts/build/contracts/ERC1967Proxy.json"


def get_w3():
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
    return w3


nonce_tracker = {"nonce": None}


def get_nonce(w3, account):
    if nonce_tracker["nonce"] is None:
        nonce_tracker["nonce"] = w3.eth.get_transaction_count(account.address)
    nonce = nonce_tracker["nonce"]
    nonce_tracker["nonce"] += 1
    return nonce


def deploy_contract(w3, account, abi, bytecode, *constructor_args):
    contract = w3.eth.contract(abi=abi, bytecode=bytecode)
    tx = contract.constructor(*constructor_args).build_transaction({
        "from": account.address,
        "nonce": get_nonce(w3, account),
        "gas": 5_000_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": CHAIN_ID,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"  Deployed at: {receipt.contractAddress} (tx: {tx_hash.hex()})")
    return receipt.contractAddress


def deploy_proxy(w3, account, impl_address, impl_abi, init_method, *init_args):
    """Deploy a UUPS proxy pointing to an implementation, calling initialize."""
    impl = w3.eth.contract(address=impl_address, abi=impl_abi)
    init_data = impl.functions[init_method](*init_args).build_transaction({
        "from": account.address,
    })["data"]

    # Use OZ ERC1967Proxy
    proxy_path = CONTRACTS_DIR / PROXY_ARTIFACT
    if not proxy_path.exists():
        # Fallback: deploy using hardhat artifacts
        proxy_path = CONTRACTS_DIR / "artifacts" / "@openzeppelin" / "contracts" / "proxy" / "ERC1967" / "ERC1967Proxy.sol" / "ERC1967Proxy.json"

    if proxy_path.exists():
        with open(proxy_path) as f:
            proxy_artifact = json.load(f)
        proxy_address = deploy_contract(
            w3, account, proxy_artifact["abi"], proxy_artifact["bytecode"],
            impl_address, init_data
        )
    else:
        # Manual minimal proxy deployment
        print("  WARNING: ERC1967Proxy artifact not found, deploying without proxy")
        proxy_address = impl_address

    return proxy_address


def send_tx(w3, account, contract, method, *args):
    tx = contract.functions[method](*args).build_transaction({
        "from": account.address,
        "nonce": get_nonce(w3, account),
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": CHAIN_ID,
    })
    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)


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
    print(f"Balance: {w3.from_wei(balance, 'ether')} ETH")
    print()

    artifacts_dir = CONTRACTS_DIR / "artifacts" / "src"

    # --- Deploy implementations ---

    print("Deploying AgentRegistry implementation...")
    with open(artifacts_dir / "AgentRegistry.sol" / "AgentRegistry.json") as f:
        ar_artifact = json.load(f)
    ar_impl = deploy_contract(w3, account, ar_artifact["abi"], ar_artifact["bytecode"])

    print("Deploying AgentRegistry proxy...")
    ar_proxy = deploy_proxy(w3, account, ar_impl, ar_artifact["abi"], "initialize", RESOLVER_ADDRESS)

    print("Deploying PolicyRegistry implementation...")
    with open(artifacts_dir / "PolicyRegistry.sol" / "PolicyRegistry.json") as f:
        pr_artifact = json.load(f)
    pr_impl = deploy_contract(w3, account, pr_artifact["abi"], pr_artifact["bytecode"])

    print("Deploying PolicyRegistry proxy...")
    pr_proxy = deploy_proxy(w3, account, pr_impl, pr_artifact["abi"], "initialize", ar_proxy)

    print("Deploying WarrantyPool implementation...")
    with open(artifacts_dir / "WarrantyPool.sol" / "WarrantyPool.json") as f:
        wp_artifact = json.load(f)
    wp_impl = deploy_contract(w3, account, wp_artifact["abi"], wp_artifact["bytecode"])

    print("Deploying WarrantyPool proxy...")
    wp_proxy = deploy_proxy(w3, account, wp_impl, wp_artifact["abi"], "initialize", ar_proxy)

    print("Deploying ClaimManager implementation...")
    with open(artifacts_dir / "ClaimManager.sol" / "ClaimManager.json") as f:
        cm_artifact = json.load(f)
    cm_impl = deploy_contract(w3, account, cm_artifact["abi"], cm_artifact["bytecode"])

    print("Deploying ClaimManager proxy...")
    cm_proxy = deploy_proxy(w3, account, cm_impl, cm_artifact["abi"], "initialize", wp_proxy, ar_proxy, RESOLVER_ADDRESS)

    print("Deploying Heartbeat...")
    with open(artifacts_dir / "Heartbeat.sol" / "Heartbeat.json") as f:
        hb_artifact = json.load(f)
    hb_addr = deploy_contract(w3, account, hb_artifact["abi"], hb_artifact["bytecode"], ar_proxy)

    # --- Cross-contract wiring ---

    print("\nConfiguring WarrantyPool.setClaimManager...")
    wp_contract = w3.eth.contract(address=wp_proxy, abi=wp_artifact["abi"])
    send_tx(w3, account, wp_contract, "setClaimManager", cm_proxy)
    print("  Done")

    print("Configuring AgentRegistry.setWarrantyPool...")
    ar_contract = w3.eth.contract(address=ar_proxy, abi=ar_artifact["abi"])
    send_tx(w3, account, ar_contract, "setWarrantyPool", wp_proxy)
    print("  Done")

    print("\n--- Deployment Complete (UUPS Proxies) ---")
    print(f"AGENT_REGISTRY_ADDRESS={ar_proxy}")
    print(f"AGENT_REGISTRY_IMPL={ar_impl}")
    print(f"POLICY_REGISTRY_ADDRESS={pr_proxy}")
    print(f"POLICY_REGISTRY_IMPL={pr_impl}")
    print(f"WARRANTY_POOL_ADDRESS={wp_proxy}")
    print(f"WARRANTY_POOL_IMPL={wp_impl}")
    print(f"CLAIM_MANAGER_ADDRESS={cm_proxy}")
    print(f"CLAIM_MANAGER_IMPL={cm_impl}")
    print(f"HEARTBEAT_ADDRESS={hb_addr}")
    print("\nAdd the proxy addresses to your .env file.")
    print("Implementation addresses are needed for upgrades.")


if __name__ == "__main__":
    main()
