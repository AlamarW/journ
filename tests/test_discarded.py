"""journ used to destroy discarded editor text. These are the tests that keep it destroyed
never again -- and that keep the recovery copy from becoming a plaintext leak on a journal
whose whole promise is that entries never touch disk in plaintext.
"""

from datetime import date

import pytest

from journ import actions, config, crypto, discarded
from journ.builtin_editor import EditorResult

SECRET = "the quiet thing I typed and then discarded by mistake"


@pytest.fixture
def discard_dir(tmp_path, monkeypatch):
    path = tmp_path / "discarded"
    monkeypatch.setattr(config, "journ_discard_dir", path)
    return path


@pytest.fixture
def key():
    salt, _ = crypto.setup_passphrase("correct horse battery staple")
    return crypto.derive_key("correct horse battery staple", salt)


class TestStashing:
    def test_plaintext_when_the_journal_has_no_passphrase(self, discard_dir):
        """No passphrase means journ already stores entries in the clear; a plaintext stash
        is no weaker than the journal sitting beside it."""
        path = discarded.stash(SECRET, key=None)

        assert path.suffix == ".txt"
        assert path.read_text(encoding="utf-8") == SECRET

    def test_encrypted_when_the_journal_has_a_passphrase(self, discard_dir, key):
        path = discarded.stash(SECRET, key)

        assert path.suffix == ".enc"
        assert SECRET.encode("utf-8") not in path.read_bytes()

    def test_an_encrypted_stash_round_trips(self, discard_dir, key):
        path = discarded.stash(SECRET, key)
        assert discarded.read(path, key) == SECRET

    def test_reading_an_encrypted_stash_without_the_key_refuses(self, discard_dir, key):
        """Returning ciphertext as if it were prose would be worse than saying no."""
        path = discarded.stash(SECRET, key)

        with pytest.raises(LookupError):
            discarded.read(path, key=None)

    def test_the_filename_carries_the_entry_date(self, discard_dir):
        path = discarded.stash(SECRET, key=None, entry_date=date(2026, 7, 1))
        assert path.name.startswith("2026-07-01")

    def test_stashes_are_listed_newest_first(self, discard_dir):
        discard_dir.mkdir(parents=True)
        for name in ("2026-07-01-090000.txt", "2026-07-03-090000.txt", "2026-07-02-090000.txt"):
            (discard_dir / name).write_text("x", encoding="utf-8")

        assert [p.name for p in discarded.all_stashes()] == [
            "2026-07-03-090000.txt",
            "2026-07-02-090000.txt",
            "2026-07-01-090000.txt",
        ]

    def test_unrelated_files_are_ignored(self, discard_dir):
        discard_dir.mkdir(parents=True)
        (discard_dir / "notes.md").write_text("x", encoding="utf-8")
        assert discarded.all_stashes() == []

    def test_no_directory_means_no_stashes(self, discard_dir):
        assert discarded.all_stashes() == []


class TestDiscardingAnEditorSession:
    @pytest.fixture
    def discarding_editor(self, monkeypatch):
        """Stand in for the user typing something and then confirming a discard."""

        def use(text):
            monkeypatch.setattr(
                actions,
                "run_builtin_editor",
                lambda *args, **kwargs: EditorResult(text=text, private=False, saved=False),
            )
            monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)

        return use

    def test_discarded_text_is_kept_instead_of_destroyed(
        self, db, discard_dir, discarding_editor, capsys
    ):
        """The regression this whole change exists to prevent."""
        db.create_profile(writing_goal=750)
        discarding_editor(SECRET)

        actions.write_today_entry(db)

        stashes = discarded.all_stashes()
        assert len(stashes) == 1
        assert discarded.read(stashes[0], key=None) == SECRET
        assert "your text was kept" in capsys.readouterr().out

    def test_a_discard_still_writes_no_entry(self, db, discard_dir, discarding_editor):
        db.create_profile(writing_goal=750)
        discarding_editor(SECRET)

        actions.write_today_entry(db)

        assert db.get_entry(date.today()) is None

    def test_an_untouched_editor_stashes_nothing(
        self, db, discard_dir, discarding_editor, capsys
    ):
        """Opening the editor and closing it again should not litter the recovery folder."""
        db.create_profile(writing_goal=750)
        discarding_editor("")

        actions.write_today_entry(db)

        assert discarded.all_stashes() == []
        assert "No changes saved" in capsys.readouterr().out


class TestRecoverCommand:
    def test_says_so_when_there_is_nothing_kept(self, db, discard_dir, capsys):
        actions.recover_discarded(db)
        assert "No discarded text has been kept" in capsys.readouterr().out

    def test_lists_what_was_kept(self, db, discard_dir, capsys):
        discarded.stash(SECRET, key=None)
        actions.recover_discarded(db)

        out = capsys.readouterr().out
        assert "Discarded text kept for recovery" in out
        assert "plaintext" in out

    def test_prints_a_plaintext_stash(self, db, discard_dir, capsys):
        discarded.stash(SECRET, key=None)
        actions.recover_discarded(db, 1)
        assert SECRET in capsys.readouterr().out.replace("\n", " ")

    def test_an_out_of_range_number_is_refused(self, db, discard_dir, capsys):
        discarded.stash(SECRET, key=None)
        actions.recover_discarded(db, 5)

        out = capsys.readouterr().out
        assert "No discarded text no. 5" in out
        assert SECRET not in out

    def test_zero_is_refused_rather_than_wrapping_to_the_last(self, db, discard_dir, capsys):
        """Positions are 1-based; 0 would otherwise index the newest by accident."""
        discarded.stash(SECRET, key=None)
        actions.recover_discarded(db, 0)
        assert "No discarded text no. 0" in capsys.readouterr().out
