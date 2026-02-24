"""Seed script: register 3 demo agents with policies for instant testability."""

import httpx
import json
import sys

BASE = "http://localhost:8000/api"

DEMO_AGENTS = [
    {
        "wallet_address": "0x1111111111111111111111111111111111111111",
        "metadata_uri": "ipfs://QmDemo1-FinanceAgent",
        "policy": {
            "allowed_tools": ["get_price", "get_portfolio", "calculate_risk"],
            "prohibited_targets": ["0xdead000000000000000000000000000000000000"],
            "max_value_per_action": 1000,
            "max_slippage_bps": 50,
            "max_actions_per_window": 100,
            "window_seconds": 3600,
            "required_data_freshness_seconds": 300,
        },
    },
    {
        "wallet_address": "0x2222222222222222222222222222222222222222",
        "metadata_uri": "ipfs://QmDemo2-ResearchAgent",
        "policy": {
            "allowed_tools": ["web_search", "summarize", "extract_data"],
            "prohibited_targets": [],
            "max_value_per_action": 0,
            "max_actions_per_window": 50,
            "window_seconds": 1800,
        },
    },
    {
        "wallet_address": "0x3333333333333333333333333333333333333333",
        "metadata_uri": "ipfs://QmDemo3-TradingAgent",
        "policy": {
            "allowed_tools": ["place_order", "get_balance", "get_market_data"],
            "prohibited_targets": [
                "0xdead000000000000000000000000000000000000",
                "0xbad0000000000000000000000000000000000000",
            ],
            "max_value_per_action": 500,
            "max_actions_per_window": 20,
            "window_seconds": 600,
            "required_data_freshness_seconds": 60,
        },
    },
]


def main():
    print("Seeding AgentBond with 3 demo agents...\n")

    for i, demo in enumerate(DEMO_AGENTS, 1):
        # Register agent
        r = httpx.post(f"{BASE}/agents", json={
            "wallet_address": demo["wallet_address"],
            "metadata_uri": demo["metadata_uri"],
        })
        if r.status_code != 200:
            print(f"  Failed to register agent {i}: {r.text}")
            continue
        agent = r.json()
        agent_id = agent["id"]
        print(f"Agent {i}: ID={agent_id}, metadata={demo['metadata_uri']}")

        # Register policy
        r = httpx.post(f"{BASE}/policies", json={
            "agent_id": agent_id,
            "rules": demo["policy"],
        })
        if r.status_code != 200:
            print(f"  Failed to register policy: {r.text}")
            continue
        policy = r.json()
        print(f"  Policy: ID={policy['id']}, hash={policy['policy_hash'][:16]}...")

        # Stake collateral (record)
        r = httpx.post(f"{BASE}/agents/{agent_id}/stake", json={
            "amount_wei": "100000000000000000",  # 0.1 ETH
        })
        if r.status_code == 200:
            print(f"  Staked: 0.1 ETH")

        print()

    print("Seed complete! Run 'make demo' for end-to-end test.")


if __name__ == "__main__":
    main()
