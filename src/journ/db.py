"""SQLite-backed repository for the single local profile and its journal entries.

Replaces the old module-level global `cursor`/`conn` with a context manager opened per
command, which is what makes the test suite able to point at an isolated temp file instead
of the user's real ~/.journ/journal.db.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from journ.models import JournalEntry, Profile

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    writing_goal INTEGER NOT NULL DEFAULT 750,
    streak INTEGER NOT NULL DEFAULT 0,
    streak_last_entry_date TEXT,
    kdf_salt BLOB,
    passphrase_canary BLOB
);

CREATE TABLE IF NOT EXISTS journal_entry (
    entry_date TEXT PRIMARY KEY,
    content BLOB NOT NULL,
    is_encrypted INTEGER NOT NULL,
    words_per_minute REAL,
    accomplished_goal INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
"""

_PROFILE_COLUMNS = (
    "writing_goal, streak, streak_last_entry_date, kdf_salt, passphrase_canary, longest_streak"
)
_ENTRY_COLUMNS = (
    "entry_date, content, is_encrypted, words_per_minute, accomplished_goal, updated_at, "
    "word_count, started_at"
)


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})"))


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive schema upgrades for dbs created before analytics support was added.

    Safe to run on every connect: each step is guarded by a column-existence check, so it's
    a no-op once a database is up to date.
    """
    if not _column_exists(conn, "journal_entry", "word_count"):
        conn.execute("ALTER TABLE journal_entry ADD COLUMN word_count INTEGER")
        # Left NULL on purpose -- backfilling would require decrypting every entry, which
        # would force a passphrase prompt just to open the database. Database.update_word_count
        # backfills lazily, the first time each entry is decrypted for another reason.

    if not _column_exists(conn, "journal_entry", "started_at"):
        conn.execute("ALTER TABLE journal_entry ADD COLUMN started_at TEXT")
        conn.execute("UPDATE journal_entry SET started_at = updated_at WHERE started_at IS NULL")

    if not _column_exists(conn, "profile", "longest_streak"):
        conn.execute("ALTER TABLE profile ADD COLUMN longest_streak INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "UPDATE profile SET longest_streak = streak WHERE longest_streak < streak"
        )

    conn.commit()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.executescript(_SCHEMA)
        self.conn.commit()
        _migrate(self.conn)

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.conn.commit()
        self.conn.close()

    # --- profile ---

    def get_profile(self) -> Profile | None:
        row = self.conn.execute(
            f"SELECT {_PROFILE_COLUMNS} FROM profile WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return self._row_to_profile(row)

    def create_profile(
        self,
        writing_goal: int,
        kdf_salt: bytes | None = None,
        passphrase_canary: bytes | None = None,
    ) -> Profile:
        self.conn.execute(
            "INSERT INTO profile (id, writing_goal, streak, streak_last_entry_date, kdf_salt, "
            "passphrase_canary, longest_streak) VALUES (1, ?, 0, NULL, ?, ?, 0)",
            (writing_goal, kdf_salt, passphrase_canary),
        )
        return Profile(
            writing_goal=writing_goal,
            streak=0,
            streak_last_entry_date=None,
            kdf_salt=kdf_salt,
            passphrase_canary=passphrase_canary,
            longest_streak=0,
        )

    def update_goal(self, writing_goal: int) -> None:
        self.conn.execute("UPDATE profile SET writing_goal = ? WHERE id = 1", (writing_goal,))

    def update_streak(self, streak: int, last_entry_date: date | None) -> None:
        self.conn.execute(
            "UPDATE profile SET streak = ?, streak_last_entry_date = ? WHERE id = 1",
            (streak, last_entry_date.isoformat() if last_entry_date else None),
        )

    def update_longest_streak(self, longest_streak: int) -> None:
        self.conn.execute(
            "UPDATE profile SET longest_streak = ? WHERE id = 1", (longest_streak,)
        )

    def set_passphrase(self, kdf_salt: bytes | None, canary: bytes | None) -> None:
        self.conn.execute(
            "UPDATE profile SET kdf_salt = ?, passphrase_canary = ? WHERE id = 1",
            (kdf_salt, canary),
        )

    # --- entries ---

    def get_entry(self, entry_date: date) -> JournalEntry | None:
        row = self.conn.execute(
            f"SELECT {_ENTRY_COLUMNS} FROM journal_entry WHERE entry_date = ?",
            (entry_date.isoformat(),),
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def latest_entry(self) -> JournalEntry | None:
        row = self.conn.execute(
            f"SELECT {_ENTRY_COLUMNS} FROM journal_entry ORDER BY entry_date DESC LIMIT 1"
        ).fetchone()
        return self._row_to_entry(row) if row else None

    def all_entries(self) -> list[JournalEntry]:
        rows = self.conn.execute(
            f"SELECT {_ENTRY_COLUMNS} FROM journal_entry ORDER BY entry_date"
        ).fetchall()
        return [self._row_to_entry(row) for row in rows]

    def upsert_entry(self, entry: JournalEntry) -> None:
        self.conn.execute(
            f"INSERT INTO journal_entry ({_ENTRY_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(entry_date) DO UPDATE SET content=excluded.content, "
            "is_encrypted=excluded.is_encrypted, words_per_minute=excluded.words_per_minute, "
            "accomplished_goal=excluded.accomplished_goal, updated_at=excluded.updated_at, "
            "word_count=excluded.word_count, started_at=excluded.started_at",
            (
                entry.entry_date.isoformat(),
                entry.content,
                int(entry.is_encrypted),
                entry.words_per_minute,
                int(entry.accomplished_goal),
                entry.updated_at,
                entry.word_count,
                entry.started_at,
            ),
        )

    def update_word_count(self, entry_date: date, word_count: int) -> None:
        """Lazily backfills word_count for entries written before it was tracked, the first
        time each one is decrypted for another reason (see _migrate)."""
        self.conn.execute(
            "UPDATE journal_entry SET word_count = ? WHERE entry_date = ?",
            (word_count, entry_date.isoformat()),
        )

    def aggregate_totals(self) -> tuple[int, int]:
        """Returns (total_words, entry_count) from stored word_count metadata only -- no
        decryption needed. Entries with a NULL word_count (not yet backfilled) are excluded
        from the word total but still counted as entries."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(word_count), 0), COUNT(*) FROM journal_entry"
        ).fetchone()
        return row[0], row[1]

    @staticmethod
    def _row_to_profile(row) -> Profile:
        (
            writing_goal,
            streak,
            streak_last_entry_date,
            kdf_salt,
            passphrase_canary,
            longest_streak,
        ) = row
        return Profile(
            writing_goal=writing_goal,
            streak=streak,
            streak_last_entry_date=(
                date.fromisoformat(streak_last_entry_date) if streak_last_entry_date else None
            ),
            kdf_salt=kdf_salt,
            passphrase_canary=passphrase_canary,
            longest_streak=longest_streak,
        )

    @staticmethod
    def _row_to_entry(row) -> JournalEntry:
        (
            entry_date,
            content,
            is_encrypted,
            words_per_minute,
            accomplished_goal,
            updated_at,
            word_count,
            started_at,
        ) = row
        return JournalEntry(
            entry_date=date.fromisoformat(entry_date),
            content=content,
            is_encrypted=bool(is_encrypted),
            words_per_minute=words_per_minute,
            accomplished_goal=bool(accomplished_goal),
            updated_at=updated_at,
            word_count=word_count,
            started_at=started_at,
        )
