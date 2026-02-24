"""AgentBond CLI - Operator management tool."""

import json
import sys

import click
import httpx

BASE_URL = "http://localhost:8000/api"


def api_get(path: str):
    r = httpx.get(f"{BASE_URL}{path}")
    r.raise_for_status()
    return r.json()


def api_post(path: str, data: dict):
    r = httpx.post(f"{BASE_URL}{path}", json=data)
    r.raise_for_status()
    return r.json()


@click.group()
def cli():
    """AgentBond - Verifiable Agent Warranty Network CLI"""
    pass


# --- Agent commands ---


@cli.group()
def agent():
    """Manage agents."""
    pass


@agent.command("register")
@click.option("--wallet", required=True, help="Operator wallet address")
@click.option("--metadata-uri", required=True, help="Agent metadata URI")
def agent_register(wallet: str, metadata_uri: str):
    """Register a new agent."""
    result = api_post("/agents", {
        "wallet_address": wallet,
        "metadata_uri": metadata_uri,
    })
    click.echo(f"Agent registered: ID={result['id']}")
    click.echo(json.dumps(result, indent=2))


@agent.command("list")
def agent_list():
    """List all agents."""
    agents = api_get("/agents")
    if not agents:
        click.echo("No agents registered.")
        return
    for a in agents:
        status = a.get("status", "unknown")
        click.echo(
            f"  #{a['id']}  score={a['trust_score']}  "
            f"runs={a['total_runs']}  violations={a['violations']}  "
            f"status={status}"
        )


@agent.command("info")
@click.argument("agent_id", type=int)
def agent_info(agent_id: int):
    """Get agent details."""
    result = api_get(f"/agents/{agent_id}")
    click.echo(json.dumps(result, indent=2))


@agent.command("status")
@click.argument("agent_id", type=int)
@click.argument("new_status", type=click.Choice(["active", "paused", "retired"]))
def agent_status(agent_id: int, new_status: str):
    """Set agent status."""
    result = api_post(f"/agents/{agent_id}/status", {"status": new_status})
    click.echo(f"Agent #{agent_id} status set to: {result['status']}")


# --- Staking commands ---


@cli.group()
def stake():
    """Manage staking."""
    pass


@stake.command("deposit")
@click.argument("agent_id", type=int)
@click.argument("amount_wei")
def stake_deposit(agent_id: int, amount_wei: str):
    """Stake collateral for an agent."""
    result = api_post(f"/agents/{agent_id}/stake", {"amount_wei": amount_wei})
    click.echo(f"Staked {amount_wei} wei for agent #{agent_id}")


@stake.command("withdraw")
@click.argument("agent_id", type=int)
@click.argument("amount_wei")
def stake_withdraw(agent_id: int, amount_wei: str):
    """Request unstake for an agent."""
    result = api_post(f"/agents/{agent_id}/unstake", {"amount_wei": amount_wei})
    click.echo(f"Unstake requested: {amount_wei} wei for agent #{agent_id}")


# --- Policy commands ---


@cli.group()
def policy():
    """Manage policies."""
    pass


@policy.command("register")
@click.argument("agent_id", type=int)
@click.option("--rules-file", required=True, type=click.Path(exists=True), help="JSON rules file")
def policy_register(agent_id: int, rules_file: str):
    """Register a policy from a JSON file."""
    with open(rules_file) as f:
        rules = json.load(f)
    result = api_post("/policies", {"agent_id": agent_id, "rules": rules})
    click.echo(f"Policy registered: ID={result['id']}, hash={result['policy_hash'][:16]}...")


@policy.command("list")
@click.option("--agent-id", type=int, default=None)
def policy_list(agent_id: int | None):
    """List policies."""
    params = f"?agent_id={agent_id}" if agent_id else ""
    policies = api_get(f"/policies{params}")
    for p in policies:
        click.echo(f"  #{p['id']}  agent={p['agent_id']}  status={p['status']}")


@policy.command("activate")
@click.argument("policy_id", type=int)
@click.argument("agent_id", type=int)
def policy_activate(policy_id: int, agent_id: int):
    """Activate a policy for an agent."""
    result = api_post(f"/policies/{policy_id}/activate", {"agent_id": agent_id})
    click.echo(f"Policy #{policy_id} activated for agent #{agent_id}")


# --- Run commands ---


@cli.group()
def run():
    """Execute and inspect runs."""
    pass


@run.command("execute")
@click.argument("agent_id", type=int)
@click.option("--input", "user_input", required=True, help="User input for the agent")
def run_execute(agent_id: int, user_input: str):
    """Execute an agent run."""
    result = api_post("/runs", {
        "agent_id": agent_id,
        "user_input": user_input,
    })
    click.echo(f"Run ID: {result['run_id']}")
    click.echo(f"Verdict: {result['policy_verdict']}")
    if result.get("reason_codes"):
        click.echo(f"Violations: {', '.join(result['reason_codes'])}")
    click.echo(f"Settlement TX: {result.get('settlement_tx', 'N/A')}")


@run.command("info")
@click.argument("run_id")
def run_info(run_id: str):
    """Get run details."""
    result = api_get(f"/runs/{run_id}")
    click.echo(json.dumps(result, indent=2))


@run.command("replay")
@click.argument("run_id")
def run_replay(run_id: str):
    """Re-verify a run independently."""
    result = api_get(f"/runs/{run_id}/replay")
    click.echo(f"Proof Valid: {result['proof_valid']}")
    click.echo(f"Re-evaluated Verdict: {result['policy_verdict']}")
    click.echo(f"Original Verdict: {result['original_verdict']}")
    if result.get("reason_codes"):
        click.echo(f"Violations: {', '.join(result['reason_codes'])}")


# --- Claim commands ---


@cli.group()
def claim():
    """Manage claims."""
    pass


@claim.command("submit")
@click.argument("run_id")
@click.argument("agent_id", type=int)
@click.option("--claimant", required=True, help="Claimant wallet address")
@click.option("--reason", required=True, type=click.Choice([
    "TOOL_WHITELIST_VIOLATION", "VALUE_LIMIT_EXCEEDED", "PROHIBITED_TARGET",
    "FREQUENCY_EXCEEDED", "STALE_DATA", "MODEL_MISMATCH"
]))
def claim_submit(run_id: str, agent_id: int, claimant: str, reason: str):
    """Submit a warranty claim."""
    result = api_post("/claims", {
        "run_id": run_id,
        "agent_id": agent_id,
        "claimant_address": claimant,
        "reason_code": reason,
    })
    click.echo(f"Claim #{result['claim_id']}: {result['status']}")
    click.echo(f"Approved: {result['approved']}")
    click.echo(f"Reason: {result['reason']}")


@claim.command("list")
@click.option("--agent-id", type=int, default=None)
def claim_list(agent_id: int | None):
    """List claims."""
    params = f"?agent_id={agent_id}" if agent_id else ""
    claims = api_get(f"/claims{params}")
    for c in claims:
        click.echo(f"  #{c['id']}  agent={c['agent_id']}  reason={c['reason_code']}  status={c['status']}")


# --- Score commands ---


@cli.group()
def score():
    """Query reputation scores."""
    pass


@score.command("get")
@click.argument("agent_id", type=int)
def score_get(agent_id: int):
    """Get trust score for an agent."""
    result = api_get(f"/scores/{agent_id}")
    click.echo(f"Agent #{agent_id} Trust Score: {result['score']}/100")
    click.echo(f"  Total Runs: {result['total_runs']}")
    click.echo(f"  Violations: {result['violations']}")
    if result.get("breakdown"):
        b = result["breakdown"]
        click.echo(f"  Breakdown:")
        click.echo(f"    Base: {b['base']}")
        click.echo(f"    Violation Penalty: -{b['violation_penalty']}")
        click.echo(f"    Claim Penalty: -{b['claim_penalty']}")
        click.echo(f"    Recency Bonus: +{b['recency_bonus']}")


# --- Dashboard ---


@cli.command("stats")
def stats():
    """Show global dashboard stats."""
    result = api_get("/dashboard/stats")
    click.echo(f"AgentBond Network Stats:")
    click.echo(f"  Agents: {result['total_agents']}")
    click.echo(f"  Runs: {result['total_runs']}")
    click.echo(f"  Claims: {result['total_claims']}")
    click.echo(f"  Paid Claims: {result['paid_claims']}")
    click.echo(f"  Violations: {result['total_violations']}")


if __name__ == "__main__":
    cli()
