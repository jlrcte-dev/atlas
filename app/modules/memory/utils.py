"""Utilities for the memory module."""

from __future__ import annotations

import hashlib

# Telegram callback_data has a 64-byte hard limit.
# Format `fb:<src>:<ref>:<sig>` reserves ~9 chars of overhead, leaving ~55 for ref.
# 32 is a safe budget that fits Gmail message IDs unchanged and produces
# collision-resistant hashes for URLs.
_REF_MAX = 32


def to_callback_ref(raw: str, max_len: int = _REF_MAX) -> str:
    """Return a short, deterministic reference safe for Telegram callback_data.

    If `raw` already fits within max_len, return it unchanged so that
    natural identifiers (e.g. Gmail message IDs) remain readable in the DB.
    Otherwise return an md5 hex digest truncated to `max_len`.
    Empty input returns an empty string.

    The same function MUST be used on both the writing path (memory logging)
    and the reading path (Telegram callback parsing) so that lookups match.
    """
    if not raw:
        return ""
    if len(raw) <= max_len:
        return raw
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:max_len]
