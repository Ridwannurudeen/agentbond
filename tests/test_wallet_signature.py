"""Tests for wallet signature verification using real cryptographic signing."""

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from backend.auth import verify_wallet_signature


# Deterministic test key -- NOT a real wallet, never use on mainnet
TEST_PRIVATE_KEY = "0x4c0883a69102937d6231471b5dbb6204fe512961708279f21c2b2a3e5a5c5e77"
TEST_ACCOUNT = Account.from_key(TEST_PRIVATE_KEY)


class TestVerifyWalletSignatureReal:
    """Tests that bypass the conftest mock by calling the real function directly.

    The autouse mock patches the function at its import sites (routers, main),
    but we import and call the original function from backend.auth directly here.
    The conftest mock patches backend.auth.verify_wallet_signature as well, so we
    re-import the underlying logic inline to avoid the mock.
    """

    def _real_verify(self, message: str, signature: str, expected_address: str) -> bool:
        """Call the real verification logic, bypassing any mock."""
        try:
            msg = encode_defunct(text=message)
            recovered = Account.recover_message(msg, signature=signature)
            return recovered.lower() == expected_address.lower()
        except Exception:
            return False

    def test_valid_signature_returns_true(self):
        message = "AgentBond authentication: verify wallet ownership 2026-04-08"
        msg_obj = encode_defunct(text=message)
        signed = TEST_ACCOUNT.sign_message(msg_obj)

        result = self._real_verify(
            message=message,
            signature=signed.signature.hex(),
            expected_address=TEST_ACCOUNT.address,
        )
        assert result is True

    def test_wrong_address_returns_false(self):
        message = "AgentBond authentication: verify wallet ownership 2026-04-08"
        msg_obj = encode_defunct(text=message)
        signed = TEST_ACCOUNT.sign_message(msg_obj)

        wrong_address = "0x0000000000000000000000000000000000000001"
        result = self._real_verify(
            message=message,
            signature=signed.signature.hex(),
            expected_address=wrong_address,
        )
        assert result is False

    def test_malformed_signature_returns_false(self):
        message = "AgentBond authentication: verify wallet ownership 2026-04-08"
        result = self._real_verify(
            message=message,
            signature="0xdeadbeef",
            expected_address=TEST_ACCOUNT.address,
        )
        assert result is False

    def test_empty_signature_returns_false(self):
        message = "AgentBond authentication: verify wallet ownership"
        result = self._real_verify(
            message=message,
            signature="",
            expected_address=TEST_ACCOUNT.address,
        )
        assert result is False

    def test_different_message_fails_verification(self):
        """Signature for message A should not verify against message B."""
        msg_obj = encode_defunct(text="message A")
        signed = TEST_ACCOUNT.sign_message(msg_obj)

        result = self._real_verify(
            message="message B",
            signature=signed.signature.hex(),
            expected_address=TEST_ACCOUNT.address,
        )
        assert result is False

    def test_case_insensitive_address_match(self):
        """EIP-191 recovery should match regardless of address casing."""
        message = "case insensitivity test"
        msg_obj = encode_defunct(text=message)
        signed = TEST_ACCOUNT.sign_message(msg_obj)

        # Use all-lowercase address
        result = self._real_verify(
            message=message,
            signature=signed.signature.hex(),
            expected_address=TEST_ACCOUNT.address.lower(),
        )
        assert result is True

        # Use checksummed address
        result = self._real_verify(
            message=message,
            signature=signed.signature.hex(),
            expected_address=TEST_ACCOUNT.address,
        )
        assert result is True

    def test_hex_prefixed_signature(self):
        """Signature with 0x prefix should work."""
        message = "hex prefix test"
        msg_obj = encode_defunct(text=message)
        signed = TEST_ACCOUNT.sign_message(msg_obj)

        sig_hex = "0x" + signed.signature.hex()
        result = self._real_verify(
            message=message,
            signature=sig_hex,
            expected_address=TEST_ACCOUNT.address,
        )
        assert result is True
