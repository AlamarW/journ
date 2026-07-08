"""Passphrase-based encryption for journal entry content.

A passphrase, when set, protects entry *content* itself (not just app access) via a key
derived with PBKDF2-HMAC-SHA256 and Fernet (AES-128-CBC + HMAC) symmetric encryption.
Fernet verifies integrity on decrypt, so a single encrypted "canary" value doubles as the
passphrase-correctness check -- no separate password hash is stored.
"""

from __future__ import annotations

import base64
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PBKDF2_ITERATIONS = 600_000
CANARY = b"journ-passphrase-canary"


def generate_salt() -> bytes:
    return os.urandom(16)


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode("utf-8")))


def setup_passphrase(passphrase: str) -> tuple[bytes, bytes]:
    """Returns (kdf_salt, encrypted_canary) to persist on the profile."""
    salt = generate_salt()
    key = derive_key(passphrase, salt)
    canary = Fernet(key).encrypt(CANARY)
    return salt, canary


def verify_passphrase(passphrase: str, salt: bytes, canary: bytes) -> bytes | None:
    """Returns the derived Fernet key if the passphrase is correct, else None."""
    key = derive_key(passphrase, salt)
    try:
        if Fernet(key).decrypt(canary) == CANARY:
            return key
    except InvalidToken:
        pass
    return None


def encrypt_text(key: bytes, text: str) -> bytes:
    return Fernet(key).encrypt(text.encode("utf-8"))


def decrypt_text(key: bytes, blob: bytes) -> str:
    return Fernet(key).decrypt(blob).decode("utf-8")
