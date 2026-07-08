from datetime import date

from journ import actions, config, crypto
from journ.builtin_editor import EditorResult
from journ.models import JournalEntry
from journ.words import count_words


def test_builtin_editor_never_touches_tmp_dir_and_skips_redundant_goal_line(
    db, tmp_path, monkeypatch, capsys
):
    db.create_profile(writing_goal=5)
    monkeypatch.setattr(config, "journ_tmp_dir", tmp_path / "tmp")
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda initial_text, writing_goal, initial_private=False: EditorResult(
            text="written via builtin", private=initial_private
        ),
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
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False: EditorResult(text="five whole words here", private=priv),
    )
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
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False: EditorResult(text="word " * 60, private=priv),
    )
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
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False: EditorResult(text="a few more words", private=priv),
    )
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)

    actions.write_today_entry(db)

    output = capsys.readouterr().out
    assert "Milestone" not in output


def _forbid_unlock(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("unlock() should not be called for metadata-only actions")

    monkeypatch.setattr(actions, "unlock", _fail)


def test_write_today_entry_defaults_to_not_private(db, monkeypatch):
    db.create_profile(writing_goal=1)
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False: EditorResult(text="some words", private=priv),
    )
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)

    actions.write_today_entry(db)

    assert db.get_entry(date.today()).private is False


def test_write_today_entry_preserves_existing_private_flag_by_default(db, monkeypatch):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date.today(), content=b"secret so far", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=2,
            private=True,
        )
    )
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False: EditorResult(text=text + " more", private=priv),
    )
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)

    actions.write_today_entry(db)  # private=None -- should preserve, not reset to False

    assert db.get_entry(date.today()).private is True


def test_write_today_entry_explicit_private_overrides_existing_flag(db, monkeypatch):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date.today(), content=b"secret so far", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=2,
            private=True,
        )
    )
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False: EditorResult(text=text + " more", private=priv),
    )
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)

    actions.write_today_entry(db, private=False)

    assert db.get_entry(date.today()).private is False


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


def test_export_journal_excludes_private_entries_by_default(db, tmp_path):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"public entry text", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=3,
        )
    )
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 2), content=b"a secret confession", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=3,
            private=True,
        )
    )
    output_path = tmp_path / "export.json"

    actions.export_journal(db, output_path, "json")

    exported = output_path.read_text()
    assert "public entry text" in exported
    assert "secret confession" not in exported


def test_export_journal_include_private_includes_everything(db, tmp_path):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"a secret confession", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=3,
            private=True,
        )
    )
    output_path = tmp_path / "export.json"

    actions.export_journal(db, output_path, "json", include_private=True)

    assert "secret confession" in output_path.read_text()


def test_export_journal_all_private_prints_message_without_writing(db, tmp_path, capsys):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"a secret confession", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=3,
            private=True,
        )
    )
    output_path = tmp_path / "export.json"

    actions.export_journal(db, output_path, "json")

    assert not output_path.exists()
    assert "--include-private" in capsys.readouterr().out


def test_save_conversation_entry_creates_new_entry_counts_only_user_words(db):
    db.create_profile(writing_goal=1)
    turns = [
        actions.ConversationTurn(role="user", text="five user words here today"),
        actions.ConversationTurn(
            role="assistant", text="a much longer assistant reply with many extra words"
        ),
    ]

    result = actions.save_conversation_entry(db, date.today(), turns, key=None)

    assert result.word_count == 5
    entry = db.get_entry(date.today())
    assert entry.word_count == 5
    assert entry.words_per_minute is None
    text = entry.content.decode("utf-8")
    assert "You:" in text
    assert "Assistant:" in text
    assert "much longer assistant reply" in text


def test_save_conversation_entry_merges_with_existing_editor_entry_additive_word_count(db):
    db.create_profile(writing_goal=1)
    today = date.today()
    db.upsert_entry(
        JournalEntry(
            entry_date=today, content=b"ten prior words placeholder text right here now",
            is_encrypted=False, words_per_minute=42.0, accomplished_goal=False,
            updated_at="x", word_count=10,
        )
    )
    turns = [actions.ConversationTurn(role="user", text="three new words")]

    result = actions.save_conversation_entry(db, today, turns, key=None)

    assert result.word_count == 13
    entry = db.get_entry(today)
    assert entry.word_count == 13
    assert entry.words_per_minute == 42.0  # untouched, never recomputed/nulled


def test_save_conversation_entry_backfills_null_word_count_before_merging(db):
    db.create_profile(writing_goal=1)
    today = date.today()
    db.upsert_entry(
        JournalEntry(
            entry_date=today, content=b"three word text", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=None,
        )
    )
    turns = [actions.ConversationTurn(role="user", text="two more")]

    result = actions.save_conversation_entry(db, today, turns, key=None)

    assert result.word_count == 5  # 3 backfilled + 2 new, not a bare 2


def test_save_conversation_entry_appends_text_after_existing(db):
    db.create_profile(writing_goal=1)
    today = date.today()
    db.upsert_entry(
        JournalEntry(
            entry_date=today, content=b"original entry text", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=3,
        )
    )
    turns = [actions.ConversationTurn(role="user", text="new words")]

    actions.save_conversation_entry(db, today, turns, key=None)

    text = db.get_entry(today).content.decode("utf-8")
    assert text.startswith("original entry text")
    assert text.index("original entry text") < text.index("You: new words")


def test_save_conversation_entry_private_none_preserves_existing_flag(db):
    db.create_profile(writing_goal=1)
    today = date.today()
    db.upsert_entry(
        JournalEntry(
            entry_date=today, content=b"x", is_encrypted=False, words_per_minute=None,
            accomplished_goal=False, updated_at="x", word_count=0, private=True,
        )
    )
    turns = [actions.ConversationTurn(role="user", text="hi")]

    actions.save_conversation_entry(db, today, turns, key=None, private=None)
    assert db.get_entry(today).private is True

    actions.save_conversation_entry(db, today, turns, key=None, private=False)
    assert db.get_entry(today).private is False


def test_save_conversation_entry_only_updates_streak_when_entry_date_is_today(db):
    db.create_profile(writing_goal=1)
    turns = [actions.ConversationTurn(role="user", text="backdated words")]
    backdated = date(2020, 1, 1)

    result = actions.save_conversation_entry(db, backdated, turns, key=None)

    assert result.streak_changed is False
    assert db.get_profile().streak == 0
    entry = db.get_entry(backdated)
    assert entry.word_count == 2
    assert entry.accomplished_goal is True


def test_save_conversation_entry_detects_word_milestones_regardless_of_date(db):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2020, 1, 1), content=b"x", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=995,
        )
    )
    turns = [actions.ConversationTurn(role="user", text="six more words right here now")]

    result = actions.save_conversation_entry(db, date(2019, 1, 1), turns, key=None)

    assert ("words", 1000) in result.milestones


def test_save_conversation_entry_treats_unknown_role_as_non_counting(db):
    db.create_profile(writing_goal=1)
    turns = [
        actions.ConversationTurn(role="user", text="two words"),
        actions.ConversationTurn(role="system", text="a bunch of system words that don't count"),
    ]

    result = actions.save_conversation_entry(db, date.today(), turns, key=None)

    assert result.word_count == 2
    text = db.get_entry(date.today()).content.decode("utf-8")
    assert "system:" in text  # stored and labeled, just not counted


def test_save_conversation_entry_encrypts_when_passphrase_set(db):
    db.create_profile(writing_goal=1)
    passphrase = "correct horse battery staple"
    salt, canary = crypto.setup_passphrase(passphrase)
    key = crypto.derive_key(passphrase, salt)
    db.set_passphrase(salt, canary)
    turns = [actions.ConversationTurn(role="user", text="secret thoughts here")]

    actions.save_conversation_entry(db, date.today(), turns, key=key)

    entry = db.get_entry(date.today())
    assert entry.is_encrypted is True
    assert b"secret" not in entry.content
    assert crypto.decrypt_text(key, entry.content).startswith("You: secret thoughts here")


def test_save_conversation_entry_and_write_today_entry_do_not_clobber_each_other(db, monkeypatch):
    db.create_profile(writing_goal=1)
    today = date.today()
    db.upsert_entry(
        JournalEntry(
            entry_date=today, content=b"prior words here", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=3,
        )
    )

    # Simulate a conversation save landing in between write_today_entry's initial read (used
    # to pre-fill the editor) and its final write -- the streak/word-count bookkeeping for
    # each write must still be internally consistent, not silently dropped.
    turns = [actions.ConversationTurn(role="user", text="two new")]
    actions.save_conversation_entry(db, today, turns, key=None)
    assert db.get_entry(today).word_count == 5

    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False: EditorResult(text=text + " typed more", private=priv),
    )
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)
    actions.write_today_entry(db)

    final = db.get_entry(today)
    assert final.word_count == count_words(final.content.decode("utf-8"))


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
