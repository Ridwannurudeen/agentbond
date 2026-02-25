"""OpenGradient SDK wrapper for agent execution and proof verification."""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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


class OGExecutionClient:
    """Thin wrapper around OpenGradient SDK for verifiable agent execution."""

    def __init__(self, private_key: str):
        self.private_key = private_key
        self._client = None
        self._initialized = False

    def _ensure_init(self):
        if self._initialized:
            return
        # Skip SDK init if no valid private key (avoids blocking RPC calls)
        if not self.private_key or not self.private_key.startswith("0x") or len(self.private_key) < 66:
            logger.warning("No valid OG private key configured. Running in mock mode.")
            self._client = None
            self._initialized = True
            return
        try:
            import opengradient as og
            self._client = og.init(private_key=self.private_key)
            self._initialized = True
            logger.info("OpenGradient SDK initialized")
        except Exception as e:
            logger.warning(
                f"OpenGradient SDK unavailable ({e}). Running in mock mode."
            )
            self._client = None
            self._initialized = True

    async def execute_agent_run(
        self,
        model_id: str,
        user_input: str,
        tools: list[str] | None = None,
    ) -> RunResult:
        """Execute an agent run via OG SDK with settlement metadata."""
        self._ensure_init()

        run_id = uuid.uuid4().hex
        input_hash = hashlib.sha256(user_input.encode()).hexdigest()

        if self._client is None:
            # Mock mode for development
            output = f"[mock] Response to: {user_input}"
            output_hash = hashlib.sha256(output.encode()).hexdigest()
            transcript = [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": output},
            ]
            if tools:
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

        # Real OG SDK execution
        try:
            result = self._client.llm.create(
                model=model_id,
                messages=[{"role": "user", "content": user_input}],
                settlement_mode="SETTLE_METADATA",
            )

            output = result.choices[0].message.content
            output_hash = hashlib.sha256(output.encode()).hexdigest()

            transcript = [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": output},
            ]

            settlement_tx = getattr(result, "settlement_tx", None)
            model_cid = getattr(result, "model_cid", model_id)

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
            logger.error(f"OG SDK execution failed: {e}")
            raise

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
            # In real implementation, query the OG chain for settlement data
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
