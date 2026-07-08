"""OS-native secure cache for the derived Fernet key used by `journ mcp serve --content`.

Stores only the derived key (never the raw passphrase) via the `keyring` package -- Windows
Credential Manager / macOS Keychain / Linux Secret Service depending on platform. Decoupled
from Typer/CLI, same as db.py/crypto.py, so it's independently testable by monkeypatching the
three `keyring` functions it calls.
"""

from __future__ import annotations

import json
from datetime import datetime

import keyring
import keyring.errors

_SERVICE_NAME = "journ-mcp"
_USERNAME = "journal-key"  # journ has exactly one local profile, so this is a fixed key


class KeychainError(Exception):
    """Raised when the OS credential store can't be reached or returns malformed data."""


def cache_key(key: bytes) -> None:
    """Caches the derived Fernet key indefinitely (no TTL -- see journ mcp lock/status)."""
    payload = json.dumps({"key": key.decode("ascii"), "cached_at": datetime.now().isoformat()})
    try:
        keyring.set_password(_SERVICE_NAME, _USERNAME, payload)
    except keyring.errors.KeyringError as exc:
        raise KeychainError(f"Could not store the key in the OS credential store: {exc}") from exc


def get_cached_key() -> bytes | None:
    payload = _read_payload()
    if payload is None:
        return None
    try:
        return payload["key"].encode("ascii")
    except KeyError:
        return None


def get_cached_at() -> datetime | None:
    payload = _read_payload()
    if payload is None:
        return None
    try:
        return datetime.fromisoformat(payload["cached_at"])
    except (KeyError, ValueError):
        return None


def clear_cached_key() -> None:
    try:
        keyring.delete_password(_SERVICE_NAME, _USERNAME)
    except keyring.errors.PasswordDeleteError:
        pass  # already unlocked -- lock() is idempotent, same spirit as passphrase remove


def _read_payload() -> dict | None:
    try:
        raw = keyring.get_password(_SERVICE_NAME, _USERNAME)
    except keyring.errors.KeyringError:
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None  # corrupted entry -- treat as "not cached" rather than crashing
