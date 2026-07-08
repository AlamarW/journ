from datetime import datetime, timedelta

import keyring
import keyring.errors
import pytest

from journ import mcp_keychain


def test_cache_and_get_key_round_trip(fake_keyring):
    mcp_keychain.cache_key(b"derived-key-bytes")
    assert mcp_keychain.get_cached_key() == b"derived-key-bytes"


def test_get_cached_at_returns_a_recent_timestamp(fake_keyring):
    mcp_keychain.cache_key(b"derived-key-bytes")
    cached_at = mcp_keychain.get_cached_at()
    assert cached_at is not None
    assert datetime.now() - cached_at < timedelta(seconds=5)


def test_get_cached_key_returns_none_when_absent(fake_keyring):
    assert mcp_keychain.get_cached_key() is None


def test_get_cached_at_returns_none_when_absent(fake_keyring):
    assert mcp_keychain.get_cached_at() is None


def test_clear_cached_key_is_idempotent_when_nothing_cached(fake_keyring):
    mcp_keychain.clear_cached_key()
    mcp_keychain.clear_cached_key()  # should not raise


def test_clear_cached_key_removes_it(fake_keyring):
    mcp_keychain.cache_key(b"derived-key-bytes")
    mcp_keychain.clear_cached_key()
    assert mcp_keychain.get_cached_key() is None


def test_cache_key_wraps_keyring_errors_as_keychain_error(fake_keyring, monkeypatch):
    def _fail(*args, **kwargs):
        raise keyring.errors.PasswordSetError("no backend available")

    monkeypatch.setattr(keyring, "set_password", _fail)

    with pytest.raises(mcp_keychain.KeychainError):
        mcp_keychain.cache_key(b"derived-key-bytes")


def test_corrupted_payload_treated_as_not_cached(fake_keyring):
    keyring.set_password(mcp_keychain._SERVICE_NAME, mcp_keychain._USERNAME, "not valid json")

    assert mcp_keychain.get_cached_key() is None
    assert mcp_keychain.get_cached_at() is None
