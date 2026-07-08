from datetime import date

from journ import actions, config, crypto
from journ.models import JournalEntry


def test_builtin_editor_never_touches_tmp_dir_and_skips_redundant_goal_line(
    db, tmp_path, monkeypatch, capsys
):
    db.create_profile(writing_goal=5)
    monkeypatch.setattr(config, "journ_tmp_dir", tmp_path / "tmp")
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)
    monkeypatch.setattr(
        actions, "run_builtin_editor", lambda initial_text, writing_goal: "written via builtin"
    )

    actions.write_today_entry(db)

    assert not (tmp_path / "tmp").exists() or list((tmp_path / "tmp").glob("*")) == []

    entry = db.latest_entry()
    assert entry is not None
    assert entry.content.decode("utf-8") == "written via builtin"

    output = capsys.readouterr().out
    assert "over your goal" not in output
    assert "under your goal" not in output
    assert "Streak" in output or "streak" in output


def test_external_editor_still_prints_goal_line(db, tmp_path, monkeypatch, capsys):
    db.create_profile(writing_goal=5)
    stub = tmp_path / "stub.py"
    stub.write_text(
        "import sys\n"
        "with open(sys.argv[1], 'a', encoding='utf-8') as f:\n"
        "    f.write('some words written externally today')\n"
    )
    monkeypatch.setattr(config, "journ_tmp_dir", tmp_path / "tmp")
    monkeypatch.setattr(actions.config, "get_editor", lambda: f"python3 {stub}")

    actions.write_today_entry(db)

    output = capsys.readouterr().out
    assert "your goal" in output


def test_write_persists_word_count_and_started_at(db, monkeypatch):
    db.create_profile(writing_goal=1)
    monkeypatch.setattr(actions, "run_builtin_editor", lambda text, goal: "five whole words here")
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)

    actions.write_today_entry(db)

    entry = db.latest_entry()
    assert entry.word_count == 4
    assert entry.started_at is not None


def test_milestone_line_appears_when_threshold_crossed(db, monkeypatch, capsys):
    db.create_profile(writing_goal=1)
    # Seed a prior day close to the 1,000-word milestone.
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2020, 1, 1), content=b"x", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=950,
        )
    )
    monkeypatch.setattr(actions, "run_builtin_editor", lambda text, goal: "word " * 60)
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)

    actions.write_today_entry(db)

    output = capsys.readouterr().out
    assert "Milestone" in output
    assert "1,000 total words" in output


def test_milestone_does_not_reappear_on_unrelated_write(db, monkeypatch, capsys):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2020, 1, 1), content=b"x", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=2_000,
        )
    )
    monkeypatch.setattr(actions, "run_builtin_editor", lambda text, goal: "a few more words")
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)

    actions.write_today_entry(db)

    output = capsys.readouterr().out
    assert "Milestone" not in output


def _forbid_unlock(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("unlock() should not be called for metadata-only actions")

    monkeypatch.setattr(actions, "unlock", _fail)


def test_metadata_only_actions_never_prompt_for_passphrase(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    salt, canary = crypto.setup_passphrase("does-not-matter")
    db.set_passphrase(salt, canary)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"ciphertext", is_encrypted=True,
            words_per_minute=40.0, accomplished_goal=True, updated_at="2026-07-01T09:00:00",
            word_count=300, started_at="2026-07-01T08:45:00",
        )
    )
    _forbid_unlock(monkeypatch)

    actions.show_calendar(db)
    actions.show_trends(db, days=30)
    actions.show_records(db)
    actions.show_patterns(db)
    actions.suggest_goal_action(db)
    actions.show_streak(db)

    # The get_* data functions backing the MCP Tier-1 tools -- these must be safe to call
    # directly, with no ensure_profile/unlock reachable, even with no profile at all.
    actions.get_calendar_data(db)
    actions.get_trends_data(db, days=30)
    actions.get_records_data(db)
    actions.get_patterns_data(db)
    actions.get_goal_suggestion(db)
    actions.get_streak_data(db)
    actions.get_current_goal(db)
    actions.get_stats_totals(db)

    capsys.readouterr()  # just confirms none of the above raised


def test_get_records_data_returns_none_with_no_profile(db):
    assert actions.get_records_data(db) is None


def test_get_goal_suggestion_returns_none_none_with_no_profile(db):
    assert actions.get_goal_suggestion(db) == (None, None)


def test_get_streak_data_returns_zeros_with_no_profile(db):
    assert actions.get_streak_data(db) == (0, 0)


def test_get_current_goal_returns_none_with_no_profile(db):
    assert actions.get_current_goal(db) is None


def test_filter_private_excludes_unless_include_private():
    private_entry = JournalEntry(
        entry_date=date(2026, 7, 1), content=b"x", is_encrypted=False,
        words_per_minute=None, accomplished_goal=False, updated_at="x", private=True,
    )
    public_entry = JournalEntry(
        entry_date=date(2026, 7, 2), content=b"x", is_encrypted=False,
        words_per_minute=None, accomplished_goal=False, updated_at="x", private=False,
    )
    entries = [private_entry, public_entry]

    assert actions.filter_private(entries, include_private=False) == [public_entry]
    assert actions.filter_private(entries, include_private=True) == entries


def test_get_entry_by_date_returns_none_for_private_entry_when_not_included(db, monkeypatch):
    db.create_profile(writing_goal=750)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"secret thoughts", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", private=True,
        )
    )
    profile = db.get_profile()
    _forbid_unlock(monkeypatch)  # a hidden private entry must never trigger a decrypt attempt

    result = actions.get_entry_by_date(
        db, profile, key=None, entry_date=date(2026, 7, 1), include_private=False
    )
    assert result is None


def test_get_entry_by_date_returns_entry_when_include_private_true(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"secret thoughts", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", private=True,
            word_count=2,
        )
    )
    profile = db.get_profile()

    result = actions.get_entry_by_date(
        db, profile, key=None, entry_date=date(2026, 7, 1), include_private=True
    )
    assert result is not None
    assert result.text == "secret thoughts"


def test_get_entry_by_date_returns_none_for_missing_date(db):
    db.create_profile(writing_goal=750)
    profile = db.get_profile()
    result = actions.get_entry_by_date(
        db, profile, key=None, entry_date=date(2026, 7, 1), include_private=False
    )
    assert result is None


def test_set_private_marks_and_unmarks_via_action(db, capsys):
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"x", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x",
        )
    )
    actions.set_private(db, date(2026, 7, 1), True)
    assert db.get_entry(date(2026, 7, 1)).private is True
    assert "now private" in capsys.readouterr().out

    actions.set_private(db, date(2026, 7, 1), False)
    assert db.get_entry(date(2026, 7, 1)).private is False
    assert "no longer private" in capsys.readouterr().out


def test_set_private_on_missing_entry_prints_message(db, capsys):
    actions.set_private(db, date(2026, 7, 1), True)
    assert "No entry found" in capsys.readouterr().out


def test_word_frequency_decrypts_encrypted_entries(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    passphrase = "correct horse battery staple"
    salt, canary = crypto.setup_passphrase(passphrase)
    key = crypto.derive_key(passphrase, salt)
    db.set_passphrase(salt, canary)
    ciphertext = crypto.encrypt_text(key, "wandering thoughts about wandering rivers")
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=ciphertext, is_encrypted=True,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=5,
        )
    )
    monkeypatch.setattr(actions, "unlock", lambda profile, attempts=3: key)

    actions.show_word_frequency(db)

    output = capsys.readouterr().out
    assert "wandering" in output
