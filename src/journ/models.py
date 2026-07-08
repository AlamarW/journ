"""Data model for the single local profile and journal entries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class Profile:
    writing_goal: int
    streak: int
    streak_last_entry_date: date | None
    kdf_salt: bytes | None
    passphrase_canary: bytes | None

    @property
    def has_passphrase(self) -> bool:
        return self.kdf_salt is not None and self.passphrase_canary is not None


@dataclass
class JournalEntry:
    entry_date: date
    content: bytes
    is_encrypted: bool
    words_per_minute: float | None
    accomplished_goal: bool
    updated_at: str
