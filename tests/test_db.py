from datetime import date

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
