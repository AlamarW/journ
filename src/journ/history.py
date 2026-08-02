"""Prior versions of journal entries.

quire owns the store; journ supplies the codec and the target. The codec is the whole point
here: journ's entries are encrypted at rest, and a revision table holding plaintext copies
of them would quietly undo that. Prior versions are encrypted exactly like the entry they
came from.

Because the key only exists after unlocking, a store is built per call rather than held on
the Database. Passing the old key alongside the plaintext codec is what lets a journal that
gained a passphrase still read the history it wrote before it had one.
"""

from __future__ import annotations

from datetime import date

from quire.revisions import (
    AGENT,
    HUMAN,
    PlainTextCodec,
    Revision,
    RevisionStore,
    RevisionTarget,
)

from journ import crypto
from journ.db import Database

__all__ = [
    "AGENT",
    "HUMAN",
    "FernetCodec",
    "Revision",
    "entry_target",
    "history",
    "record",
    "store",
]


class FernetCodec:
    """Encrypts prior versions with the same scheme as the entries themselves."""

    name = "fernet"

    def __init__(self, key: bytes):
        self._key = key

    def encode(self, text: str) -> bytes:
        return crypto.encrypt_text(self._key, text)

    def decode(self, blob: bytes) -> str:
        return crypto.decrypt_text(self._key, bytes(blob))


def entry_target(entry_date: date) -> RevisionTarget:
    """Entries are keyed by date, which is why quire normalises record ids to strings."""
    return RevisionTarget("entry", entry_date.isoformat(), "text")


def store(db: Database, key: bytes | None) -> RevisionStore:
    """A store that writes under the current key and can still read what came before it.

    With a key, new revisions are encrypted and older plaintext ones stay readable. Without
    one, only plaintext history can be read -- an encrypted journal that has not been
    unlocked raises rather than handing back ciphertext.
    """
    codecs = [FernetCodec(key), PlainTextCodec()] if key is not None else [PlainTextCodec()]
    return RevisionStore(db.conn, codecs=codecs)


def record(
    db: Database,
    key: bytes | None,
    entry_date: date,
    previous_text: str,
    new_text: str,
    actor: str = HUMAN,
) -> None:
    """Keep the text about to be overwritten, unless there is nothing to keep: an entry that
    did not exist yet, or a save that changed nothing."""
    if not previous_text or previous_text == new_text:
        return
    store(db, key).record(entry_target(entry_date), previous_text, actor=actor)


def history(db: Database, key: bytes | None, entry_date: date) -> list[Revision]:
    """Prior versions of one day's entry, newest first."""
    return store(db, key).history(entry_target(entry_date))
