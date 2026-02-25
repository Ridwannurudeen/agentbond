"""Tests for input validation utilities."""

import pytest
from backend.validation import (
    is_valid_wallet,
    is_valid_hex_hash,
    is_valid_reason_code,
    validate_wallet,
    validate_reason_code,
    VALID_REASON_CODES,
)


class TestWalletValidation:
    def test_valid_wallet(self):
        assert is_valid_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f2bD60")

    def test_valid_wallet_lowercase(self):
        assert is_valid_wallet("0x742d35cc6634c0532925a3b844bc9e7595f2bd60")

    def test_valid_wallet_uppercase(self):
        assert is_valid_wallet("0x742D35CC6634C0532925A3B844BC9E7595F2BD60")

    def test_invalid_no_prefix(self):
        assert not is_valid_wallet("742d35Cc6634C0532925a3b844Bc9e7595f2bD60")

    def test_invalid_too_short(self):
        assert not is_valid_wallet("0x742d35Cc")

    def test_invalid_too_long(self):
        assert not is_valid_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f2bD6000")

    def test_invalid_non_hex(self):
        assert not is_valid_wallet("0xZZZd35Cc6634C0532925a3b844Bc9e7595f2bD60")

    def test_invalid_empty(self):
        assert not is_valid_wallet("")

    def test_validate_wallet_returns_lowercase(self):
        result = validate_wallet("0x742D35CC6634C0532925A3B844BC9E7595F2BD60")
        assert result == "0x742d35cc6634c0532925a3b844bc9e7595f2bd60"

    def test_validate_wallet_raises_on_invalid(self):
        with pytest.raises(ValueError, match="Invalid wallet address"):
            validate_wallet("not-a-wallet")


class TestHexHashValidation:
    def test_valid_hash_with_prefix(self):
        assert is_valid_hex_hash("0x" + "a" * 64)

    def test_valid_hash_without_prefix(self):
        assert is_valid_hex_hash("a" * 64)

    def test_invalid_hash_too_short(self):
        assert not is_valid_hex_hash("0x" + "a" * 63)

    def test_invalid_hash_non_hex(self):
        assert not is_valid_hex_hash("z" * 64)


class TestReasonCodeValidation:
    def test_all_valid_codes(self):
        for code in VALID_REASON_CODES:
            assert is_valid_reason_code(code)

    def test_invalid_code(self):
        assert not is_valid_reason_code("INVALID_CODE")

    def test_empty_code(self):
        assert not is_valid_reason_code("")

    def test_validate_reason_code_passes(self):
        result = validate_reason_code("TOOL_WHITELIST_VIOLATION")
        assert result == "TOOL_WHITELIST_VIOLATION"

    def test_validate_reason_code_raises(self):
        with pytest.raises(ValueError, match="Invalid reason code"):
            validate_reason_code("MADE_UP_CODE")
