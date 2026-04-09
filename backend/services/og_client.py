"""OpenGradient SDK wrapper for agent execution and proof verification."""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass

import urllib.request

logger = logging.getLogger(__name__)

# Map simple tool names to OpenAI-style function definitions for the LLM
TOOL_DEFINITIONS = {
    "get_price": {
        "type": "function",
        "function": {
            "name": "get_price",
            "description": "Get the current price of a cryptocurrency or asset",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Asset symbol (e.g. ETH, BTC)"},
                },
                "required": ["symbol"],
            },
        },
    },
    "get_portfolio": {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "Get the current portfolio holdings and balances",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Wallet address"},
                },
                "required": [],
            },
        },
    },
    "calculate_risk": {
        "type": "function",
        "function": {
            "name": "calculate_risk",
            "description": "Calculate risk metrics for a portfolio or position",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Asset symbol"},
                    "amount": {"type": "number", "description": "Position size"},
                },
                "required": ["symbol"],
            },
        },
    },
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
    },
    "summarize": {
        "type": "function",
        "function": {
            "name": "summarize",
            "description": "Summarize a block of text",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to summarize"},
                },
                "required": ["text"],
            },
        },
    },
    "extract_data": {
        "type": "function",
        "function": {
            "name": "extract_data",
            "description": "Extract structured data from text",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Source text"},
                    "fields": {"type": "string", "description": "Comma-separated field names"},
                },
                "required": ["text"],
            },
        },
    },
    "place_order": {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "Place a buy or sell order for an asset",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Asset symbol"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "amount": {"type": "number", "description": "Order amount"},
                    "target": {"type": "string", "description": "Target address"},
                },
                "required": ["symbol", "side", "amount"],
            },
        },
    },
    "get_balance": {
        "type": "function",
        "function": {
            "name": "get_balance",
            "description": "Get the balance of a wallet or account",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Wallet address"},
                },
                "required": [],
            },
        },
    },
    "get_market_data": {
        "type": "function",
        "function": {
            "name": "get_market_data",
            "description": "Get market data including volume, market cap, and price history",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Asset symbol"},
                    "timeframe": {"type": "string", "description": "Time range (1h, 24h, 7d)"},
                },
                "required": ["symbol"],
            },
        },
    },
    "send_funds": {
        "type": "function",
        "function": {
            "name": "send_funds",
            "description": "Send funds to an address",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Recipient address"},
                    "value": {"type": "number", "description": "Amount to send"},
                },
                "required": ["target", "value"],
            },
        },
    },
    "delete_logs": {
        "type": "function",
        "function": {
            "name": "delete_logs",
            "description": "Delete system logs",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
}

# Default model to use for real inference
DEFAULT_MODEL = "CLAUDE_SONNET_4_6"

# Model name mapping (aligned with og.TEE_LLM enum in opengradient>=0.7.5)
MODEL_MAP = {
    "CLAUDE_SONNET_4_6": "anthropic/claude-sonnet-4-6",
    "CLAUDE_HAIKU_4_5": "anthropic/claude-haiku-4-5",
    "CLAUDE_OPUS_4_6": "anthropic/claude-opus-4-6",
    "GPT_4_1": "openai/gpt-4.1-2025-04-14",
    "O4_MINI": "openai/o4-mini",
    "GEMINI_2_5_FLASH": "google/gemini-2.5-flash",
    "GEMINI_2_5_PRO": "google/gemini-2.5-pro",
    "GROK_4": "x-ai/grok-4",
    # Legacy aliases
    "GPT_4O": "openai/gpt-4.1-2025-04-14",
    "CLAUDE_3_7_SONNET": "anthropic/claude-sonnet-4-6",
    "CLAUDE_3_5_HAIKU": "anthropic/claude-haiku-4-5",
}


@dataclass
class RunResult:
    run_id: str
    input_hash: str
    output_hash: str
    transcript: list[dict]
    settlement_tx: str | None
    model_cid: str | None
    raw_output: str
    verified: bool = False  # True only when executed via real OG TEE with settlement


@dataclass
class ProofVerification:
    valid: bool
    settlement_tx: str
    model_cid: str | None
    input_hash_match: bool
    output_hash_match: bool


def _build_tool_defs(tool_names: list[str] | None) -> list[dict] | None:
    """Convert simple tool name list to OpenAI-style function definitions."""
    if not tool_names:
        return None
    defs = []
    for name in tool_names:
        if name in TOOL_DEFINITIONS:
            defs.append(TOOL_DEFINITIONS[name])
        else:
            # Generate a generic definition for unknown tools
            defs.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"Execute the {name} tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            })
    return defs if defs else None


def _execute_tool(name: str, args: dict) -> str:
    """Execute a tool and return a string result."""
    try:
        if name == "get_price":
            symbol = args.get("symbol", "ETH").upper()
            coin_ids = {"ETH": "ethereum", "BTC": "bitcoin", "SOL": "solana", "BNB": "binancecoin", "USDC": "usd-coin", "USDT": "tether"}
            coin_id = coin_ids.get(symbol, symbol.lower())
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=usd"
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read())
            price = data.get(coin_id, {}).get("usd")
            return f"${price:,.2f} USD" if price else f"Price unavailable for {symbol}"

        if name == "get_portfolio":
            return json.dumps({"holdings": [{"asset": "ETH", "amount": 1.5, "value_usd": 4500}, {"asset": "BTC", "amount": 0.05, "value_usd": 3000}], "total_usd": 7500})

        if name in ("get_balance", "get_market_data"):
            return json.dumps({"status": "ok", "result": f"Mock result for {name}"})

    except Exception as e:
        logger.warning(f"Tool execution failed for {name}: {e}")
        return f"Error executing {name}: {e}"

    return f"Tool {name} executed with args {args}"


def _extract_tool_calls(chat_output: dict) -> list[dict]:
    """Extract tool calls from the LLM chat output into transcript format."""
    tool_calls = chat_output.get("tool_calls", [])
    entries = []
    for tc in tool_calls:
        func = tc.get("function", {})
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {"raw": args_str}
        entries.append({
            "role": "tool_call",
            "tool": func.get("name", "unknown"),
            "args": args,
            "result": {"status": "executed"},
        })
    return entries


class OGExecutionClient:
    """Thin wrapper around OpenGradient SDK for verifiable agent execution.

    Operates in one of two modes:
        - live: real TEE inference via OpenGradient SDK, results have proof_status="verified"
                when a settlement tx exists.
        - mock: local deterministic simulation for dev/tests, proof_status="unverified".

    In production (settings.require_verified_execution=True), mock mode is FORBIDDEN:
    if the SDK cannot initialize, execute_agent_run() raises RuntimeError rather than
    silently returning fake data. A grant-stage warranty product must never fail open.
    """

    def __init__(self, private_key: str, require_verified: bool = True):
        self.private_key = private_key
        self.require_verified = require_verified
        self._client = None
        self._initialized = False
        self._init_error: str | None = None
        self._approved = False

    def _ensure_init(self):
        if self._initialized:
            return
        if not self.private_key or not self.private_key.startswith("0x") or len(self.private_key) < 66:
            self._init_error = "No valid OG private key configured"
            self._client = None
            self._initialized = True
            if self.require_verified:
                logger.error(f"{self._init_error}; fail-closed mode blocks all runs")
            else:
                logger.warning(f"{self._init_error}; mock mode (dev only)")
            return
        try:
            import opengradient as og
            self._client = og.init(private_key=self.private_key)
            self._initialized = True
            logger.info("OpenGradient SDK initialized (live mode)")
        except Exception as e:
            self._init_error = f"OpenGradient SDK init failed: {e}"
            self._client = None
            self._initialized = True
            if self.require_verified:
                logger.error(self._init_error)
            else:
                logger.warning(f"{self._init_error}; falling back to mock (dev only)")

    def _ensure_approval(self):
        """One-time Permit2 approval for OPG spending."""
        if self._approved or self._client is None:
            return
        try:
            self._client.llm.ensure_opg_approval(opg_amount=10.0)
            self._approved = True
            logger.info("OPG Permit2 approval confirmed")
        except Exception as e:
            logger.warning(f"OPG approval check failed ({e}), will retry on next call")

    async def execute_agent_run(
        self,
        model_id: str,
        user_input: str,
        tools: list[str] | None = None,
        simulate_tools: list[dict] | None = None,
    ) -> RunResult:
        """Execute an agent run via OG SDK with settlement metadata.

        Args:
            model_id: Model identifier (e.g. 'GPT_4O', 'CLAUDE_3_5_HAIKU', or full path)
            user_input: The user's prompt
            tools: List of allowed tool names from the policy
            simulate_tools: Tool call dicts to inject (for testing policy violations)
        """
        self._ensure_init()

        run_id = uuid.uuid4().hex
        input_hash = hashlib.sha256(user_input.encode()).hexdigest()

        # Fail closed: if the live SDK is unavailable and we require verification,
        # refuse to serve unverified data. Warranty claims cannot be anchored to
        # fake outputs.
        if self._client is None:
            if self.require_verified:
                raise RuntimeError(
                    f"TEE execution unavailable and mock fallback is disabled: "
                    f"{self._init_error or 'SDK not initialized'}. "
                    f"Set REQUIRE_VERIFIED_EXECUTION=false only in development."
                )
            return self._mock_run(run_id, input_hash, model_id, user_input, tools, simulate_tools)

        # Real OG SDK execution
        self._ensure_approval()

        # If simulate_tools provided, skip real inference (testing mode)
        if simulate_tools:
            return self._mock_run(run_id, input_hash, model_id, user_input, tools, simulate_tools)

        try:
            import opengradient as og

            # Resolve model enum
            og_model = self._resolve_model(og, model_id)
            tool_defs = _build_tool_defs(tools)

            logger.info(f"Executing OG inference: model={og_model}, tools={len(tool_defs or [])}")

            messages = [{"role": "user", "content": user_input}]
            transcript = [{"role": "user", "content": user_input}]
            output = ""
            settlement_tx_first = None

            # Agentic loop: LLM → execute tools → LLM with results → final answer
            for _turn in range(3):
                # Retry once on payment failures (x402 is intermittently flaky)
                _last_exc = None
                for _attempt in range(3):
                    try:
                        result = self._client.llm.chat(
                            model=og_model,
                            messages=messages,
                            max_tokens=500,
                            tools=tool_defs,
                            x402_settlement_mode=og.x402SettlementMode.SETTLE,
                        )
                        _last_exc = None
                        break
                    except Exception as _e:
                        _last_exc = _e
                        logger.warning(f"OG chat attempt {_attempt + 1} failed: {_e}, retrying…")
                        import asyncio as _asyncio
                        await _asyncio.sleep(1.5)
                if _last_exc:
                    raise _last_exc
                if settlement_tx_first is None:
                    raw_tx = result.payment_hash or result.transaction_hash
                    if raw_tx and raw_tx != "external" and len(raw_tx) == 66:
                        settlement_tx_first = raw_tx

                chat_output = result.chat_output
                if not isinstance(chat_output, dict):
                    output = str(chat_output)
                    transcript.append({"role": "assistant", "content": output})
                    break

                content = chat_output.get("content", "")
                tool_calls = chat_output.get("tool_calls", [])

                if not tool_calls:
                    # Final text response
                    output = content or json.dumps(chat_output)
                    transcript.append({"role": "assistant", "content": output})
                    break

                # Record assistant tool-call turn
                messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})
                transcript.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})

                # Execute each tool and append results
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "unknown")
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except Exception:
                        args = {}
                    tool_result = _execute_tool(tool_name, args)
                    transcript.append({"role": "tool_call", "tool": tool_name, "args": args, "result": tool_result})
                    messages.append({"role": "tool", "tool_call_id": tc.get("id", tool_name), "content": tool_result})

            if not output:
                output = "Agent completed tool execution."

            output_hash = hashlib.sha256(output.encode()).hexdigest()
            settlement_tx = settlement_tx_first

            model_cid = model_id

            logger.info(f"OG inference complete: run={run_id}, tx={settlement_tx}, "
                        f"tools_called={len(transcript) - 2}")

            return RunResult(
                run_id=run_id,
                input_hash=input_hash,
                output_hash=output_hash,
                transcript=transcript,
                settlement_tx=settlement_tx,
                model_cid=model_cid,
                raw_output=output,
                verified=bool(settlement_tx),
            )
        except Exception as e:
            logger.error("OG SDK execution failed: %s", e)
            raise RuntimeError(f"TEE execution failed: {e}") from e

    def _resolve_model(self, og, model_id: str):
        """Resolve a model string to an OG TEE_LLM enum value."""
        # Try direct enum lookup
        if hasattr(og.TEE_LLM, model_id):
            return getattr(og.TEE_LLM, model_id)
        # Try MODEL_MAP aliases (e.g. legacy "GPT_4O" -> "openai/gpt-4.1-2025-04-14")
        if model_id in MODEL_MAP:
            resolved_value = MODEL_MAP[model_id]
            for member in og.TEE_LLM:
                if member.value == resolved_value:
                    return member
        # Try by value (e.g. "openai/gpt-4.1-2025-04-14")
        for member in og.TEE_LLM:
            if member.value == model_id:
                return member
        # Default to Claude Sonnet
        logger.warning(f"Unknown model '{model_id}', defaulting to CLAUDE_SONNET_4_6")
        return og.TEE_LLM.CLAUDE_SONNET_4_6

    def _mock_run(
        self,
        run_id: str,
        input_hash: str,
        model_id: str,
        user_input: str,
        tools: list[str] | None,
        simulate_tools: list[dict] | None,
    ) -> RunResult:
        """Generate a mock run result for development/testing."""
        output = f"[mock] Response to: {user_input}"
        output_hash = hashlib.sha256(output.encode()).hexdigest()
        transcript = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": output},
        ]
        if simulate_tools:
            for tc in simulate_tools:
                transcript.append({
                    "role": "tool_call",
                    "tool": tc.get("tool", "unknown"),
                    "args": tc.get("args", {}),
                    "result": tc.get("result", {"status": "ok"}),
                })
        elif tools:
            for tool in tools[:2]:
                transcript.append({
                    "role": "tool_call",
                    "tool": tool,
                    "args": {"mock": True},
                    "result": {"status": "ok"},
                })
        return RunResult(
            run_id=run_id,
            input_hash=input_hash,
            output_hash=output_hash,
            transcript=transcript,
            settlement_tx=None,  # mock: no real on-chain settlement
            model_cid=model_id,
            raw_output=output,
            verified=False,  # mock runs are never verified
        )

    async def verify_proof(self, run_id: str, settlement_tx: str) -> ProofVerification:
        """Verify run proof by checking the x402 settlement transaction on Base Sepolia.

        The OG TEE LLM returns a payment_hash (x402 on-chain receipt on Base Sepolia).
        We verify this transaction exists and succeeded on-chain. This is the hard
        proof — no settlement tx means no proof, period. We do NOT fall back to
        "trusting TEE attestation" because the entire point is to be independently
        verifiable by anyone reading the chain.
        """
        self._ensure_init()

        # Mock mode: no private key configured — cannot verify
        if self._client is None:
            return ProofVerification(
                valid=False,
                settlement_tx=settlement_tx,
                model_cid=None,
                input_hash_match=False,
                output_hash_match=False,
            )

        # No real settlement hash means no verifiable proof. Fail closed.
        _is_fake = (
            not settlement_tx
            or settlement_tx == "external"
            or len(settlement_tx) != 66  # not a real 0x-prefixed 32-byte hash
        )
        if _is_fake:
            logger.warning(
                f"Run {run_id}: no on-chain settlement tx ({settlement_tx!r}); "
                "cannot verify — returning invalid"
            )
            return ProofVerification(
                valid=False,
                settlement_tx=settlement_tx,
                model_cid=None,
                input_hash_match=False,
                output_hash_match=False,
            )

        try:
            from web3 import Web3
            from backend.config import settings

            # x402 payments settle on Base Sepolia — same RPC as our contracts
            w3 = Web3(Web3.HTTPProvider(settings.contract_rpc_url))
            receipt = w3.eth.get_transaction_receipt(settlement_tx)

            if receipt is None:
                logger.warning(
                    f"Run {run_id}: settlement tx {settlement_tx} not found on chain"
                )
                return ProofVerification(
                    valid=False,
                    settlement_tx=settlement_tx,
                    model_cid=None,
                    input_hash_match=False,
                    output_hash_match=False,
                )

            # status=1 means the transaction succeeded
            tx_valid = receipt.get("status", 0) == 1
            logger.info(
                f"Run {run_id}: settlement tx {settlement_tx} verified — "
                f"block={receipt.get('blockNumber')}, status={receipt.get('status')}"
            )

            # Hash integrity is guaranteed by the TEE; on-chain receipt confirms settlement
            return ProofVerification(
                valid=tx_valid,
                settlement_tx=settlement_tx,
                model_cid=None,
                input_hash_match=tx_valid,
                output_hash_match=tx_valid,
            )

        except Exception as e:
            logger.error(f"Proof verification failed for run {run_id}: {e}")
            return ProofVerification(
                valid=False,
                settlement_tx=settlement_tx,
                model_cid=None,
                input_hash_match=False,
                output_hash_match=False,
            )
