"""End-to-end demo: register -> stake -> execute run -> violate policy -> claim -> verify."""

import httpx
import json
import time

BASE = "http://localhost:8000/api"


def main():
    print("=" * 60)
    print("  AgentBond End-to-End Demo")
    print("=" * 60)

    # 1. Register agent
    print("\n[1] Registering agent...")
    r = httpx.post(f"{BASE}/agents", json={
        "wallet_address": "0xDEMO000000000000000000000000000000000001",
        "metadata_uri": "ipfs://QmDemoE2E-Agent",
    })
    agent = r.json()
    agent_id = agent["id"]
    print(f"    Agent ID: {agent_id}")

    # 2. Register policy (strict: only allow get_price)
    print("\n[2] Registering strict policy...")
    r = httpx.post(f"{BASE}/policies", json={
        "agent_id": agent_id,
        "rules": {
            "allowed_tools": ["get_price"],
            "max_value_per_action": 100,
            "prohibited_targets": ["0xdead000000000000000000000000000000000000"],
            "max_actions_per_window": 5,
            "window_seconds": 60,
        },
    })
    policy = r.json()
    print(f"    Policy ID: {policy['id']}")

    # 3. Stake collateral
    print("\n[3] Staking collateral...")
    r = httpx.post(f"{BASE}/agents/{agent_id}/stake", json={
        "amount_wei": "50000000000000000",
    })
    print(f"    Staked: 0.05 ETH")

    # 4. Execute a clean run
    print("\n[4] Executing clean run...")
    r = httpx.post(f"{BASE}/runs", json={
        "agent_id": agent_id,
        "user_input": "What is the price of ETH?",
    })
    clean_run = r.json()
    print(f"    Run ID: {clean_run['run_id']}")
    print(f"    Verdict: {clean_run['policy_verdict']}")

    # 5. Check score after clean run
    print("\n[5] Checking score...")
    r = httpx.get(f"{BASE}/scores/{agent_id}")
    score = r.json()
    print(f"    Trust Score: {score['score']}/100")
    print(f"    Total Runs: {score['total_runs']}")

    # 6. Execute another run (this one uses mock mode, so it should still pass)
    print("\n[6] Executing second run...")
    r = httpx.post(f"{BASE}/runs", json={
        "agent_id": agent_id,
        "user_input": "Calculate risk for my portfolio",
    })
    run2 = r.json()
    print(f"    Run ID: {run2['run_id']}")
    print(f"    Verdict: {run2['policy_verdict']}")

    # 7. Replay and verify run
    print("\n[7] Replaying run for independent verification...")
    r = httpx.get(f"{BASE}/runs/{clean_run['run_id']}/replay")
    replay = r.json()
    print(f"    Proof Valid: {replay['proof_valid']}")
    print(f"    Re-evaluated: {replay['policy_verdict']}")
    print(f"    Original: {replay['original_verdict']}")

    # 8. Submit a claim (attempt with TOOL_WHITELIST_VIOLATION)
    print("\n[8] Submitting claim...")
    r = httpx.post(f"{BASE}/claims", json={
        "run_id": clean_run["run_id"],
        "agent_id": agent_id,
        "claimant_address": "0xCLAIMANT0000000000000000000000000000001",
        "reason_code": "TOOL_WHITELIST_VIOLATION",
    })
    claim = r.json()
    print(f"    Claim ID: {claim.get('claim_id', 'N/A')}")
    print(f"    Status: {claim.get('status', 'N/A')}")
    print(f"    Approved: {claim.get('approved', 'N/A')}")
    print(f"    Reason: {claim.get('reason', 'N/A')}")

    # 9. Final score check
    print("\n[9] Final score check...")
    r = httpx.get(f"{BASE}/scores/{agent_id}")
    final_score = r.json()
    print(f"    Trust Score: {final_score['score']}/100")
    print(f"    Total Runs: {final_score['total_runs']}")
    print(f"    Violations: {final_score['violations']}")

    # 10. Dashboard stats
    print("\n[10] Dashboard stats...")
    r = httpx.get(f"{BASE}/dashboard/stats")
    stats = r.json()
    print(f"    Total Agents: {stats['total_agents']}")
    print(f"    Total Runs: {stats['total_runs']}")
    print(f"    Total Claims: {stats['total_claims']}")

    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
