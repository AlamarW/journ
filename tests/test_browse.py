from datetime import date

from journ import actions, browse, config
from journ.builtin_editor import EditorResult
from journ.models import JournalEntry


def _entry(entry_date, text, private=False):
    return JournalEntry(
        entry_date=entry_date,
        content=text.encode("utf-8"),
        is_encrypted=False,
        words_per_minute=None,
        accomplished_goal=False,
        updated_at="x",
        word_count=len(text.split()),
        private=private,
    )


def _scripted_input(monkeypatch, responses):
    it = iter(responses)

    def _input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise AssertionError("input() called more times than scripted") from None

    monkeypatch.setattr("builtins.input", _input)


def _forbid_input(monkeypatch):
    def _fail(prompt=""):
        raise AssertionError("input() should not be called when there's nothing to browse")

    monkeypatch.setattr("builtins.input", _fail)


def test_adjacent_entry_date_steps_forward_and_backward():
    dates = [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)]
    assert browse.adjacent_entry_date(dates, date(2026, 7, 2), 1) == date(2026, 7, 3)
    assert browse.adjacent_entry_date(dates, date(2026, 7, 2), -1) == date(2026, 7, 1)


def test_adjacent_entry_date_returns_none_past_either_boundary():
    dates = [date(2026, 7, 1), date(2026, 7, 2)]
    assert browse.adjacent_entry_date(dates, date(2026, 7, 2), 1) is None
    assert browse.adjacent_entry_date(dates, date(2026, 7, 1), -1) is None


def test_adjacent_entry_date_returns_none_for_unknown_date():
    dates = [date(2026, 7, 1)]
    assert browse.adjacent_entry_date(dates, date(2099, 1, 1), 1) is None


def test_browse_entries_reports_empty_journal(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    _forbid_input(monkeypatch)

    browse.browse_entries(db)

    assert "No entries yet" in capsys.readouterr().out


def test_browse_entries_list_then_open_entry(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "hello from the past"))
    _scripted_input(monkeypatch, ["2026-07-01", "q"])

    browse.browse_entries(db)

    output = capsys.readouterr().out
    assert "Journal entries" in output
    assert "2026-07-01" in output
    assert "hello from the past" in output


def test_browse_entries_rejects_unknown_date_and_stays_at_list(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "only entry"))
    _scripted_input(monkeypatch, ["2099-01-01", "q"])

    browse.browse_entries(db)

    assert "No entry on that date." in capsys.readouterr().out


def test_browse_entries_next_and_prev_navigate_and_hit_boundaries(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "day one"))
    db.upsert_entry(_entry(date(2026, 7, 2), "day two"))
    db.upsert_entry(_entry(date(2026, 7, 3), "day three"))
    _scripted_input(monkeypatch, ["n", "n", "p", "p", "p", "q"])

    browse.browse_entries(db, start_date=date(2026, 7, 1))

    output = capsys.readouterr().out
    assert "day one" in output
    assert "day two" in output
    assert "day three" in output
    assert "Already at the earliest entry." in output


def test_browse_entries_list_command_returns_to_list_view(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "day one"))
    db.upsert_entry(_entry(date(2026, 7, 2), "day two"))
    _scripted_input(monkeypatch, ["l", "2026-07-02", "q"])

    browse.browse_entries(db, start_date=date(2026, 7, 1))

    output = capsys.readouterr().out
    assert output.count("Journal entries") == 1
    assert "day two" in output


def test_browse_entries_edit_hands_off_and_redisplays(db, monkeypatch, capsys):
    db.create_profile(writing_goal=1)
    past = date(2026, 7, 1)
    db.upsert_entry(_entry(past, "original text"))
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False, entry_date=None: EditorResult(
            text="edited text", private=priv
        ),
    )
    _scripted_input(monkeypatch, ["e", "q"])

    browse.browse_entries(db, start_date=past)

    output = capsys.readouterr().out
    assert "edited text" in output


def test_browse_entries_excludes_private_entries_by_default(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "public entry"))
    db.upsert_entry(_entry(date(2026, 7, 2), "secret entry", private=True))
    _scripted_input(monkeypatch, ["q"])

    browse.browse_entries(db)

    output = capsys.readouterr().out
    assert "2026-07-01" in output
    assert "2026-07-02" not in output


def test_browse_entries_include_private_shows_private_entries(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "public entry"))
    db.upsert_entry(_entry(date(2026, 7, 2), "secret entry", private=True))
    _scripted_input(monkeypatch, ["q"])

    browse.browse_entries(db, include_private=True)

    output = capsys.readouterr().out
    assert "2026-07-02" in output


def test_browse_entries_eof_exits_cleanly(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "an entry"))

    def _raise_eof(prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)

    browse.browse_entries(db)  # should not raise
