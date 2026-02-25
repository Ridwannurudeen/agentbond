"""Input validation utilities."""

import re

WALLET_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
HEX_HASH_RE = re.compile(r"^(0x)?[0-9a-fA-F]{64}$")

VALID_REASON_CODES = {
    "TOOL_WHITELIST_VIOLATION",
    "VALUE_LIMIT_EXCEEDED",
    "PROHIBITED_TARGET",
    "FREQUENCY_EXCEEDED",
    "STALE_DATA",
    "MODEL_MISMATCH",
}


def is_valid_wallet(address: str) -> bool:
    return bool(WALLET_RE.match(address))


def is_valid_hex_hash(h: str) -> bool:
    return bool(HEX_HASH_RE.match(h))


def is_valid_reason_code(code: str) -> bool:
    return code in VALID_REASON_CODES


def validate_wallet(address: str) -> str:
    """Validate and return a wallet address, raising ValueError if invalid."""
    if not is_valid_wallet(address):
        raise ValueError(f"Invalid wallet address format: {address}")
    return address.lower()


def validate_reason_code(code: str) -> str:
    if not is_valid_reason_code(code):
        raise ValueError(
            f"Invalid reason code: {code}. "
            f"Valid codes: {', '.join(sorted(VALID_REASON_CODES))}"
        )
    return code
