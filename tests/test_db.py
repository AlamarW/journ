import sqlite3
from datetime import date

from journ.db import Database
from journ.models import JournalEntry


def test_no_profile_initially(db):
    assert db.get_profile() is None


def test_create_and_fetch_profile(db):
    db.create_profile(writing_goal=750)
    profile = db.get_profile()
    assert profile.writing_goal == 750
    assert profile.streak == 0
    assert profile.streak_last_entry_date is None
    assert not profile.has_passphrase


def test_update_goal(db):
    db.create_profile(writing_goal=750)
    db.update_goal(1000)
    assert db.get_profile().writing_goal == 1000


def test_update_streak(db):
    db.create_profile(writing_goal=750)
    db.update_streak(5, date(2026, 7, 1))
    profile = db.get_profile()
    assert profile.streak == 5
    assert profile.streak_last_entry_date == date(2026, 7, 1)


def test_set_and_clear_passphrase(db):
    db.create_profile(writing_goal=750)
    db.set_passphrase(b"salt-bytes", b"canary-bytes")
    profile = db.get_profile()
    assert profile.has_passphrase
    assert profile.kdf_salt == b"salt-bytes"

    db.set_passphrase(None, None)
    assert not db.get_profile().has_passphrase


def test_entry_round_trip(db):
    entry = JournalEntry(
        entry_date=date(2026, 7, 1),
        content=b"hello world",
        is_encrypted=False,
        words_per_minute=42.0,
        accomplished_goal=True,
        updated_at="2026-07-01T12:00:00",
    )
    db.upsert_entry(entry)

    fetched = db.get_entry(date(2026, 7, 1))
    assert fetched.content == b"hello world"
    assert fetched.accomplished_goal is True

    assert db.get_entry(date(2026, 7, 2)) is None


def test_upsert_overwrites_existing_entry(db):
    original = JournalEntry(
        entry_date=date(2026, 7, 1),
        content=b"draft",
        is_encrypted=False,
        words_per_minute=10.0,
        accomplished_goal=False,
        updated_at="2026-07-01T09:00:00",
    )
    db.upsert_entry(original)

    updated = JournalEntry(
        entry_date=date(2026, 7, 1),
        content=b"final version",
        is_encrypted=False,
        words_per_minute=20.0,
        accomplished_goal=True,
        updated_at="2026-07-01T18:00:00",
    )
    db.upsert_entry(updated)

    fetched = db.get_entry(date(2026, 7, 1))
    assert fetched.content == b"final version"
    assert fetched.accomplished_goal is True
    assert len(db.all_entries()) == 1


def test_latest_and_all_entries(db):
    for day, text in [(1, b"first"), (2, b"second"), (3, b"third")]:
        db.upsert_entry(
            JournalEntry(
                entry_date=date(2026, 7, day),
                content=text,
                is_encrypted=False,
                words_per_minute=1.0,
                accomplished_goal=True,
                updated_at="2026-07-01T00:00:00",
            )
        )

    assert db.latest_entry().content == b"third"
    assert [e.content for e in db.all_entries()] == [b"first", b"second", b"third"]


def test_new_entries_have_word_count_and_started_at(db):
    entry = JournalEntry(
        entry_date=date(2026, 7, 1),
        content=b"hello world",
        is_encrypted=False,
        words_per_minute=42.0,
        accomplished_goal=True,
        updated_at="2026-07-01T12:00:00",
        word_count=2,
        started_at="2026-07-01T11:58:00",
    )
    db.upsert_entry(entry)
    fetched = db.get_entry(date(2026, 7, 1))
    assert fetched.word_count == 2
    assert fetched.started_at == "2026-07-01T11:58:00"


def test_update_word_count_backfills_existing_entry(db):
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1),
            content=b"ciphertext",
            is_encrypted=True,
            words_per_minute=None,
            accomplished_goal=False,
            updated_at="2026-07-01T00:00:00",
            word_count=None,
        )
    )
    db.update_word_count(date(2026, 7, 1), 123)
    assert db.get_entry(date(2026, 7, 1)).word_count == 123


def test_aggregate_totals_sums_word_count_and_counts_all_entries(db):
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"x", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=100,
        )
    )
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 2), content=b"x", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=None,
        )
    )
    total_words, entry_count = db.aggregate_totals()
    assert total_words == 100  # NULL word_count excluded from the sum
    assert entry_count == 2  # but still counted as an entry


def test_update_longest_streak(db):
    db.create_profile(writing_goal=750)
    db.update_longest_streak(12)
    assert db.get_profile().longest_streak == 12


def test_migration_adds_columns_and_backfills_existing_v2_database(tmp_path):
    """Simulates opening a database created before analytics support existed: the
    journal_entry/profile tables exist but lack the new columns entirely."""
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            writing_goal INTEGER NOT NULL DEFAULT 750,
            streak INTEGER NOT NULL DEFAULT 0,
            streak_last_entry_date TEXT,
            kdf_salt BLOB,
            passphrase_canary BLOB
        );
        CREATE TABLE journal_entry (
            entry_date TEXT PRIMARY KEY,
            content BLOB NOT NULL,
            is_encrypted INTEGER NOT NULL,
            words_per_minute REAL,
            accomplished_goal INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.execute(
        "INSERT INTO profile (id, writing_goal, streak, streak_last_entry_date, kdf_salt, "
        "passphrase_canary) VALUES (1, 750, 5, '2026-07-01', NULL, NULL)"
    )
    conn.execute(
        "INSERT INTO journal_entry (entry_date, content, is_encrypted, words_per_minute, "
        "accomplished_goal, updated_at) VALUES ('2026-07-01', 'legacy text', 0, 55.0, 1, "
        "'2026-07-01T20:00:00')"
    )
    conn.commit()
    conn.close()

    db = Database(path)
    try:
        profile = db.get_profile()
        assert profile.longest_streak == 5  # backfilled to at least the existing streak

        entry = db.get_entry(date(2026, 7, 1))
        assert entry.word_count is None  # left NULL -- would need decryption to backfill
        assert entry.started_at == "2026-07-01T20:00:00"  # backfilled from updated_at
    finally:
        db.conn.close()


def test_migration_is_idempotent_on_an_already_migrated_database(tmp_path):
    path = tmp_path / "journal.db"
    with Database(path) as db1:
        db1.create_profile(writing_goal=750)

    with Database(path) as db2:  # reopening should not error or duplicate columns
        assert db2.get_profile().writing_goal == 750
