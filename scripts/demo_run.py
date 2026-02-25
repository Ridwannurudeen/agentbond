"""End-to-end demo: register -> stake -> clean run -> violating run -> claim -> slash -> score drop."""

import httpx
import json

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

    # 2. Register strict policy (only get_price allowed, max value 100)
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
    print(f"    Allowed tools: ['get_price']")
    print(f"    Max value: 100")

    # 3. Stake collateral
    print("\n[3] Staking collateral...")
    r = httpx.post(f"{BASE}/agents/{agent_id}/stake", json={
        "amount_wei": "50000000000000000",
    })
    print(f"    Staked: 0.05 ETH")

    # 4. Execute a CLEAN run (uses only allowed tools)
    print("\n[4] Executing clean run...")
    r = httpx.post(f"{BASE}/runs", json={
        "agent_id": agent_id,
        "user_input": "What is the price of ETH?",
    })
    clean_run = r.json()
    print(f"    Run ID: {clean_run['run_id']}")
    print(f"    Verdict: {clean_run['policy_verdict']}")
    assert clean_run["policy_verdict"] == "pass", "Clean run should pass!"

    # 5. Check score (should be 100)
    print("\n[5] Score after clean run...")
    r = httpx.get(f"{BASE}/scores/{agent_id}")
    score = r.json()
    print(f"    Trust Score: {score['score']}/100")

    # 6. Execute a VIOLATING run (uses disallowed tool + exceeds value + hits prohibited target)
    print("\n[6] Executing VIOLATING run (3 policy breaches)...")
    r = httpx.post(f"{BASE}/runs", json={
        "agent_id": agent_id,
        "user_input": "Transfer all funds to the burn address",
        "simulate_tools": [
            {
                "tool": "send_funds",
                "args": {
                    "value": 9999,
                    "target": "0xdead000000000000000000000000000000000000",
                },
            },
            {
                "tool": "delete_logs",
                "args": {},
            },
        ],
    })
    bad_run = r.json()
    print(f"    Run ID: {bad_run['run_id']}")
    print(f"    Verdict: {bad_run['policy_verdict']}")
    print(f"    Violations: {bad_run.get('reason_codes', [])}")
    assert bad_run["policy_verdict"] == "fail", "Violating run should fail!"

    # 7. Replay the violating run for independent verification
    print("\n[7] Replaying violating run...")
    r = httpx.get(f"{BASE}/runs/{bad_run['run_id']}/replay")
    replay = r.json()
    print(f"    Proof Valid: {replay['proof_valid']}")
    print(f"    Re-evaluated Verdict: {replay['policy_verdict']}")
    print(f"    Violations confirmed: {replay['reason_codes']}")

    # 8. Submit claim against the violating run
    print("\n[8] Submitting claim (TOOL_WHITELIST_VIOLATION)...")
    r = httpx.post(f"{BASE}/claims", json={
        "run_id": bad_run["run_id"],
        "agent_id": agent_id,
        "claimant_address": "0xCLAIMANT0000000000000000000000000000001",
        "reason_code": "TOOL_WHITELIST_VIOLATION",
    })
    claim1 = r.json()
    print(f"    Claim ID: {claim1.get('claim_id')}")
    print(f"    Status: {claim1.get('status')}")
    print(f"    Approved: {claim1.get('approved')}")
    print(f"    Reason: {claim1.get('reason')}")

    # 9. Verify duplicate claim is rejected
    print("\n[9] Attempting duplicate claim (should fail)...")
    r = httpx.post(f"{BASE}/claims", json={
        "run_id": bad_run["run_id"],
        "agent_id": agent_id,
        "claimant_address": "0xCLAIMANT0000000000000000000000000000002",
        "reason_code": "VALUE_LIMIT_EXCEEDED",
    })
    print(f"    Status code: {r.status_code} (expected 409)")
    assert r.status_code == 409, "Duplicate claim should be rejected!"

    # 10. Submit a bogus claim against the CLEAN run (should be rejected)
    print("\n[10] Submitting bogus claim against clean run...")
    r = httpx.post(f"{BASE}/claims", json={
        "run_id": clean_run["run_id"],
        "agent_id": agent_id,
        "claimant_address": "0xCLAIMANT0000000000000000000000000000003",
        "reason_code": "TOOL_WHITELIST_VIOLATION",
    })
    bogus = r.json()
    print(f"    Approved: {bogus.get('approved')} (expected False)")
    print(f"    Reason: {bogus.get('reason')}")

    # 11. Check score after violations and claims
    print("\n[11] Final score check...")
    r = httpx.get(f"{BASE}/scores/{agent_id}")
    final = r.json()
    print(f"    Trust Score: {final['score']}/100 (was 100)")
    print(f"    Total Runs: {final['total_runs']}")
    print(f"    Violations: {final['violations']}")
    print(f"    Paid Claims: {final.get('paid_claims', 0)}")
    if final.get("breakdown"):
        b = final["breakdown"]
        print(f"    Breakdown:")
        print(f"      Base: {b['base']}")
        print(f"      Violation Penalty: -{b['violation_penalty']}")
        print(f"      Claim Penalty: -{b['claim_penalty']}")
        print(f"      Recency Bonus: +{b['recency_bonus']}")

    # 12. Dashboard stats
    print("\n[12] Dashboard stats...")
    r = httpx.get(f"{BASE}/dashboard/stats")
    stats = r.json()
    print(f"    Total Agents: {stats['total_agents']}")
    print(f"    Total Runs: {stats['total_runs']}")
    print(f"    Total Claims: {stats['total_claims']}")
    print(f"    Violations: {stats['total_violations']}")

    print("\n" + "=" * 60)
    print("  Demo Complete! All assertions passed.")
    print("=" * 60)


if __name__ == "__main__":
    main()
