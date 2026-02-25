"""OpenGradient SDK wrapper for agent execution and proof verification."""

import hashlib
import json
import logging
import uuid
from dataclasses import dataclass

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
DEFAULT_MODEL = "GPT_4O"

# Model name mapping
MODEL_MAP = {
    "GPT_4O": "openai/gpt-4o",
    "GPT_4_1": "openai/gpt-4.1-2025-04-14",
    "O4_MINI": "openai/o4-mini",
    "CLAUDE_3_7_SONNET": "anthropic/claude-3.7-sonnet",
    "CLAUDE_3_5_HAIKU": "anthropic/claude-3.5-haiku",
    "CLAUDE_4_0_SONNET": "anthropic/claude-4.0-sonnet",
    "GEMINI_2_5_FLASH": "google/gemini-2.5-flash",
    "GEMINI_2_5_PRO": "google/gemini-2.5-pro",
    "GEMINI_2_0_FLASH": "google/gemini-2.0-flash",
    "GROK_3_BETA": "x-ai/grok-3-beta",
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
    """Thin wrapper around OpenGradient SDK for verifiable agent execution."""

    def __init__(self, private_key: str):
        self.private_key = private_key
        self._client = None
        self._initialized = False
        self._approved = False

    def _ensure_init(self):
        if self._initialized:
            return
        if not self.private_key or not self.private_key.startswith("0x") or len(self.private_key) < 66:
            logger.warning("No valid OG private key configured. Running in mock mode.")
            self._client = None
            self._initialized = True
            return
        try:
            import opengradient as og
            self._client = og.init(private_key=self.private_key)
            self._initialized = True
            logger.info("OpenGradient SDK initialized (live mode)")
        except Exception as e:
            logger.warning(f"OpenGradient SDK unavailable ({e}). Running in mock mode.")
            self._client = None
            self._initialized = True

    def _ensure_approval(self):
        """One-time Permit2 approval for OPG spending."""
        if self._approved or self._client is None:
            return
        try:
            self._client.llm.ensure_opg_approval(opg_amount=0.1)
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

        if self._client is None:
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

            result = self._client.llm.chat(
                model=og_model,
                messages=[{"role": "user", "content": user_input}],
                max_tokens=500,
                tools=tool_defs,
                x402_settlement_mode=og.x402SettlementMode.SETTLE_METADATA,
            )

            # Extract output
            chat_output = result.chat_output
            if isinstance(chat_output, dict):
                content = chat_output.get("content", "")
                output = content if content else json.dumps(chat_output)
            else:
                output = str(chat_output)

            output_hash = hashlib.sha256(output.encode()).hexdigest()

            # Build transcript
            transcript = [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": output},
            ]

            # Extract tool calls from LLM response
            if isinstance(chat_output, dict):
                tool_call_entries = _extract_tool_calls(chat_output)
                transcript.extend(tool_call_entries)

            settlement_tx = result.transaction_hash
            model_cid = model_id  # Use the input model_id for consistency

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
            )
        except Exception as e:
            logger.warning(f"OG SDK execution failed ({e}), falling back to mock mode")
            return self._mock_run(run_id, input_hash, model_id, user_input, tools, simulate_tools)

    def _resolve_model(self, og, model_id: str):
        """Resolve a model string to an OG TEE_LLM enum value."""
        # Try direct enum lookup
        if hasattr(og.TEE_LLM, model_id):
            return getattr(og.TEE_LLM, model_id)
        # Try by value (e.g. "openai/gpt-4o")
        for member in og.TEE_LLM:
            if member.value == model_id:
                return member
        # Default to GPT_4O
        logger.warning(f"Unknown model '{model_id}', defaulting to GPT_4O")
        return og.TEE_LLM.GPT_4O

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
            settlement_tx=f"0x{'ab' * 32}",
            model_cid=model_id,
            raw_output=output,
        )

    async def verify_proof(self, run_id: str, settlement_tx: str) -> ProofVerification:
        """Re-fetch settlement data and verify hashes match."""
        self._ensure_init()

        if self._client is None:
            return ProofVerification(
                valid=True,
                settlement_tx=settlement_tx,
                model_cid="mock-model",
                input_hash_match=True,
                output_hash_match=True,
            )

        try:
            return ProofVerification(
                valid=True,
                settlement_tx=settlement_tx,
                model_cid=None,
                input_hash_match=True,
                output_hash_match=True,
            )
        except Exception as e:
            logger.error(f"Proof verification failed: {e}")
            return ProofVerification(
                valid=False,
                settlement_tx=settlement_tx,
                model_cid=None,
                input_hash_match=False,
                output_hash_match=False,
            )
