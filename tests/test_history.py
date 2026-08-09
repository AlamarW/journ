"""journ's half of revision history: which edits get recorded, that prior versions are
encrypted exactly like the entries they came from, and that rotating the passphrase takes
the history with it.

The store's own guarantees -- coalescing, revert being append-only, opaque content -- are
quire's and are tested there.
"""

from datetime import date, timedelta

import pytest

from journ import actions, crypto, history
from journ.builtin_editor import EditorResult
from journ.models import JournalEntry

TODAY = date.today()
PAST = TODAY - timedelta(days=3)


@pytest.fixture
def key():
    salt, _ = crypto.setup_passphrase("correct horse battery staple")
    return crypto.derive_key("correct horse battery staple", salt)


def put_entry(db, entry_date, text, key=None, word_count=None):
    """Write an entry the way actions do, without going through an editor."""
    content, is_encrypted = actions._encode_entry(text, key)
    db.upsert_entry(
        JournalEntry(
            entry_date=entry_date,
            content=content,
            is_encrypted=is_encrypted,
            words_per_minute=None,
            accomplished_goal=False,
            updated_at="2026-07-01T09:00:00",
            word_count=word_count if word_count is not None else len(text.split()),
            started_at=None,
            private=False,
        )
    )


def age_out_coalescing(db):
    """Push existing revisions outside quire's coalescing window so the next edit records
    its own entry rather than folding into the last one."""
    db.conn.execute("UPDATE revision SET created_at = datetime(created_at, '-1 day')")


class TestWhatGetsRecorded:
    def test_overwriting_an_entry_keeps_the_previous_text(self, db):
        history.record(db, None, PAST, "the morning version", "the evening version")

        assert [r.text for r in history.history(db, None, PAST)] == ["the morning version"]

    def test_a_brand_new_entry_records_nothing(self, db):
        """There is no prior version of a day you have not written yet."""
        history.record(db, None, PAST, "", "the first thing I wrote")

        assert history.history(db, None, PAST) == []

    def test_saving_identical_text_records_nothing(self, db):
        history.record(db, None, PAST, "unchanged", "unchanged")

        assert history.history(db, None, PAST) == []

    def test_days_do_not_share_history(self, db):
        history.record(db, None, PAST, "the past", "new")
        history.record(db, None, TODAY, "today", "new")

        assert [r.text for r in history.history(db, None, PAST)] == ["the past"]
        assert [r.text for r in history.history(db, None, TODAY)] == ["today"]


class TestEncryptionAtRest:
    def test_prior_versions_are_encrypted_when_the_journal_is(self, db, key):
        """A revision table full of plaintext copies would void journ's whole promise."""
        history.record(db, key, PAST, "a private thought", "replaced")

        stored = db.conn.execute("SELECT content, codec FROM revision").fetchone()
        assert stored[1] == "fernet"
        assert b"private" not in bytes(stored[0])

    def test_encrypted_history_round_trips(self, db, key):
        history.record(db, key, PAST, "a private thought", "replaced")

        assert [r.text for r in history.history(db, key, PAST)] == ["a private thought"]

    def test_prior_versions_are_plaintext_when_the_journal_is(self, db):
        """Without a passphrase journ already stores entries in the clear; history is no
        weaker than the journal beside it."""
        history.record(db, None, PAST, "no passphrase here", "replaced")

        assert db.conn.execute("SELECT codec FROM revision").fetchone()[0] == "plain"

    def test_a_locked_journal_refuses_rather_than_returning_ciphertext(self, db, key):
        history.record(db, key, PAST, "a private thought", "replaced")

        with pytest.raises(LookupError):
            history.history(db, None, PAST)

    def test_history_written_before_a_passphrase_stays_readable_after_one(self, db, key):
        """The reason quire records a codec name per row rather than per store."""
        history.record(db, None, PAST, "written in the clear", "replaced")
        age_out_coalescing(db)
        history.record(db, key, PAST, "written after the passphrase", "replaced again")

        assert [r.text for r in history.history(db, key, PAST)] == [
            "written after the passphrase",
            "written in the clear",
        ]


class TestPassphraseRotation:
    def test_setting_a_passphrase_encrypts_existing_history(self, db, monkeypatch):
        """journ re-encrypts every entry here. Leaving revisions under the old encoding
        would break history silently and unrecoverably."""
        db.create_profile(writing_goal=750)
        history.record(db, None, PAST, "written before the passphrase", "replaced")

        salt, canary = crypto.setup_passphrase("new passphrase")
        new_key = crypto.derive_key("new passphrase", salt)
        actions._reencrypt_all(db, None, salt, canary, new_key)

        assert db.conn.execute("SELECT codec FROM revision").fetchone()[0] == "fernet"
        assert [r.text for r in history.history(db, new_key, PAST)] == [
            "written before the passphrase"
        ]

    def test_changing_a_passphrase_moves_history_to_the_new_key(self, db, key):
        db.create_profile(writing_goal=750)
        put_entry(db, PAST, "current text", key)
        history.record(db, key, PAST, "an older version", "current text")

        salt, canary = crypto.setup_passphrase("a different passphrase")
        newer_key = crypto.derive_key("a different passphrase", salt)
        actions._reencrypt_all(db, key, salt, canary, newer_key)

        assert [r.text for r in history.history(db, newer_key, PAST)] == ["an older version"]

    def test_removing_a_passphrase_decrypts_history(self, db, key):
        db.create_profile(writing_goal=750)
        put_entry(db, PAST, "current text", key)
        history.record(db, key, PAST, "an older version", "current text")

        actions._reencrypt_all(db, key, None, None, None)

        assert db.conn.execute("SELECT codec FROM revision").fetchone()[0] == "plain"
        assert [r.text for r in history.history(db, None, PAST)] == ["an older version"]


class TestWritingSessions:
    @pytest.fixture
    def saving_editor(self, monkeypatch):
        def use(text):
            monkeypatch.setattr(
                actions,
                "run_builtin_editor",
                lambda *args, **kwargs: EditorResult(text=text, private=False, saved=True),
            )
            monkeypatch.setattr(
                actions.config, "get_editor", lambda: actions.config.BUILTIN_EDITOR
            )

        return use

    def test_a_saved_session_keeps_what_it_replaced(self, db, saving_editor):
        db.create_profile(writing_goal=1)
        put_entry(db, TODAY, "this morning's draft")
        saving_editor("this evening's draft")

        actions.write_today_entry(db)

        assert [r.text for r in history.history(db, None, TODAY)] == ["this morning's draft"]

    def test_a_discarded_session_records_no_revision(self, db, monkeypatch, tmp_path):
        """Nothing was replaced, so there is no prior version to keep -- the discarded text
        goes to the recovery stash instead."""
        monkeypatch.setattr(actions.config, "journ_discard_dir", tmp_path / "discarded")
        db.create_profile(writing_goal=1)
        put_entry(db, TODAY, "untouched")
        monkeypatch.setattr(
            actions,
            "run_builtin_editor",
            lambda *args, **kwargs: EditorResult(text="typed then dropped", private=False,
                                                saved=False),
        )
        monkeypatch.setattr(actions.config, "get_editor", lambda: actions.config.BUILTIN_EDITOR)

        actions.write_today_entry(db)

        assert history.history(db, None, TODAY) == []


class TestAgentEdits:
    def test_an_mcp_save_is_attributed_to_the_agent(self, db):
        """So a human can see later that an assistant, not they, changed the day's entry."""
        db.create_profile(writing_goal=750)
        put_entry(db, TODAY, "what I wrote myself")

        actions.save_conversation_entry(
            db,
            TODAY,
            [actions.ConversationTurn(role="user", text="and this from a conversation")],
            key=None,
        )

        revisions = history.history(db, None, TODAY)
        assert [(r.text, r.actor) for r in revisions] == [("what I wrote myself", "agent")]

    def test_an_mcp_save_to_an_empty_day_records_nothing(self, db):
        db.create_profile(writing_goal=750)

        actions.save_conversation_entry(
            db,
            TODAY,
            [actions.ConversationTurn(role="user", text="first words of the day")],
            key=None,
        )

        assert history.history(db, None, TODAY) == []


class TestRevert:
    def test_restores_the_previous_version(self, db, capsys):
        db.create_profile(writing_goal=750)
        put_entry(db, PAST, "the version I liked")
        history.record(db, None, PAST, "the version I liked", "the regrettable one")
        put_entry(db, PAST, "the regrettable one")

        actions.revert_entry(db, PAST)

        entry = db.get_entry(PAST)
        assert actions._decode_entry(db, entry, None) == "the version I liked"

    def test_word_count_follows_the_restored_text(self, db):
        db.create_profile(writing_goal=750)
        put_entry(db, PAST, "one two three four")
        history.record(db, None, PAST, "one two three four", "short")
        put_entry(db, PAST, "short")

        actions.revert_entry(db, PAST)

        assert db.get_entry(PAST).word_count == 4

    def test_the_replaced_text_is_kept(self, db):
        db.create_profile(writing_goal=750)
        put_entry(db, PAST, "original")
        history.record(db, None, PAST, "original", "the text being replaced")
        put_entry(db, PAST, "the text being replaced")

        actions.revert_entry(db, PAST)

        assert "the text being replaced" in [r.text for r in history.history(db, None, PAST)]

    def test_a_revert_stays_encrypted(self, db, key, monkeypatch):
        db.create_profile(writing_goal=750)
        monkeypatch.setattr(actions, "unlock", lambda profile, attempts=3: key)
        put_entry(db, PAST, "the version I liked", key)
        history.record(db, key, PAST, "the version I liked", "the regrettable one")
        put_entry(db, PAST, "the regrettable one", key)

        actions.revert_entry(db, PAST)

        entry = db.get_entry(PAST)
        assert entry.is_encrypted
        assert b"version I liked" not in entry.content
        assert actions._decode_entry(db, entry, key) == "the version I liked"

    def test_an_entry_with_no_history_says_so(self, db, capsys):
        db.create_profile(writing_goal=750)
        put_entry(db, PAST, "only ever this")

        actions.revert_entry(db, PAST)

        assert "No earlier versions" in capsys.readouterr().out

    def test_a_missing_entry_says_so(self, db, capsys):
        db.create_profile(writing_goal=750)

        actions.revert_entry(db, PAST)

        assert "No entry for" in capsys.readouterr().out

    def test_an_out_of_range_version_is_refused(self, db, capsys):
        db.create_profile(writing_goal=750)
        put_entry(db, PAST, "current")
        history.record(db, None, PAST, "older", "current")

        actions.revert_entry(db, PAST, 5)

        assert "No version 5" in capsys.readouterr().out
        assert actions._decode_entry(db, db.get_entry(PAST), None) == "current"


class TestHistoryOutput:
    def test_lists_earlier_versions(self, db, capsys):
        db.create_profile(writing_goal=750)
        history.record(db, None, PAST, "the first thing", "the second thing")

        actions.show_entry_history(db, PAST)

        assert "the first thing" in capsys.readouterr().out

    def test_says_so_when_there_is_no_history(self, db, capsys):
        db.create_profile(writing_goal=750)

        actions.show_entry_history(db, PAST)

        assert "No earlier versions" in capsys.readouterr().out
