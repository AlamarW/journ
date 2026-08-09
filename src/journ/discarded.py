"""Recovery copies of discarded editor text.

journ used to throw discarded text away outright -- `self.result = None` and the session
was gone. The two-press confirmation came across from stet after a mistyped discard cost a
real 600-word session; the recovery copy did not, because stet writes plaintext markdown
and journ could not.

That was a real constraint, not an oversight, so the answer here is not to copy stet's
behaviour but to match journ's own storage rules: a stash is encoded exactly the way the
entry itself would have been. With a passphrase set it is Fernet ciphertext, so nothing
readable reaches the disk; without one, journ already stores entries in the clear and a
plaintext stash is no weaker than the journal beside it.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from journ import config, crypto

ENCRYPTED_SUFFIX = ".enc"
PLAINTEXT_SUFFIX = ".txt"


def stash(text: str, key: bytes | None, entry_date: date | None = None) -> Path:
    """Write a recovery copy of discarded text and return its path.

    Encoded with the same rule as the entry it came from: encrypted when the journal is
    encrypted. The suffix says which, so recovery does not have to guess."""
    config.journ_discard_dir.mkdir(parents=True, exist_ok=True)
    day = (entry_date or date.today()).isoformat()
    stamp = datetime.now().strftime("%H%M%S")
    if key is not None:
        path = config.journ_discard_dir / f"{day}-{stamp}{ENCRYPTED_SUFFIX}"
        path.write_bytes(crypto.encrypt_text(key, text))
    else:
        path = config.journ_discard_dir / f"{day}-{stamp}{PLAINTEXT_SUFFIX}"
        path.write_text(text, encoding="utf-8")
    return path


def all_stashes() -> list[Path]:
    """Every recovery copy, newest first."""
    if not config.journ_discard_dir.is_dir():
        return []
    stashes = [
        path
        for path in config.journ_discard_dir.iterdir()
        if path.suffix in (ENCRYPTED_SUFFIX, PLAINTEXT_SUFFIX)
    ]
    return sorted(stashes, reverse=True)


def is_encrypted(path: Path) -> bool:
    return path.suffix == ENCRYPTED_SUFFIX


def read(path: Path, key: bytes | None) -> str:
    """Decode one recovery copy. Raises LookupError when the passphrase is needed and was
    not supplied, rather than returning ciphertext as if it were prose."""
    if not is_encrypted(path):
        return path.read_text(encoding="utf-8")
    if key is None:
        raise LookupError(f"{path.name} is encrypted -- unlock the journal to read it")
    return crypto.decrypt_text(key, path.read_bytes())
