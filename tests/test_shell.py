from datetime import date

from journ import shell as shell_module
from journ.models import JournalEntry
from journ.shell import _HELP_GROUPS, JournalingShell


def test_help_groups_exclude_alias_noise():
    # journ/EOF are backward-compat aliases for write/exit, not separate commands --
    # checking the source of truth is more robust than string-matching printed output
    # (whose title, "journ commands", would otherwise make a substring check misfire).
    listed_commands = {name for _, names in _HELP_GROUPS for name in names}
    assert "journ" not in listed_commands
    assert "EOF" not in listed_commands


def test_help_lists_grouped_commands(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)

    shell.do_help("")

    output = capsys.readouterr().out
    for section in ("Write", "Analytics", "Configuration", "Shell"):
        assert section in output
    for command in ("write", "calendar", "search", "editor", "passphrase", "exit"):
        assert command in output


def test_help_with_argument_shows_single_command_detail(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)

    shell.do_help("write")

    output = capsys.readouterr().out
    assert "Write today's entry" in output
    # Shouldn't fall through to the full grouped table for a specific command.
    assert "Analytics" not in output


def test_do_private_marks_and_unmarks_entry(db, capsys):
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1),
            content=b"x",
            is_encrypted=False,
            words_per_minute=None,
            accomplished_goal=False,
            updated_at="x",
        )
    )
    shell = JournalingShell(db)

    shell.do_private("2026-07-01")
    assert db.get_entry(date(2026, 7, 1)).private is True
    assert "now private" in capsys.readouterr().out

    shell.do_private("2026-07-01 unset")
    assert db.get_entry(date(2026, 7, 1)).private is False
    assert "no longer private" in capsys.readouterr().out


def test_do_private_rejects_bad_date(db, capsys):
    shell = JournalingShell(db)
    shell.do_private("not-a-date")
    assert "YYYY-MM-DD" in capsys.readouterr().out


def test_do_write_rejects_unknown_argument(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)
    shell.do_write("nonsense")
    assert "Usage: write" in capsys.readouterr().out


def test_do_edit_rejects_bad_date(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)
    shell.do_edit("not-a-date")
    assert "YYYY-MM-DD" in capsys.readouterr().out


def test_do_edit_rejects_unknown_flag(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)
    shell.do_edit("2026-07-01 nonsense")
    assert "Usage: edit" in capsys.readouterr().out


def test_do_edit_rejects_no_argument(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)
    shell.do_edit("")
    assert "Usage: edit" in capsys.readouterr().out


def test_do_read_rejects_bad_date(db, capsys):
    db.create_profile(writing_goal=750)
    shell = JournalingShell(db)
    shell.do_read("not-a-date")
    assert "YYYY-MM-DD" in capsys.readouterr().out


def test_do_read_parses_date_and_include_private_token(db, monkeypatch):
    # browse_entries launches a full-screen Textual app, which isn't drivable through a
    # scripted builtins.input() (Textual reads raw terminal bytes via its own driver) -- so
    # this only verifies do_read parses its arguments and calls through correctly.
    db.create_profile(writing_goal=750)
    calls = []
    monkeypatch.setattr(
        shell_module.browse,
        "browse_entries",
        lambda db, start_date=None, include_private=False: calls.append(
            (start_date, include_private)
        ),
    )
    shell = JournalingShell(db)

    shell.do_read("")
    assert calls[-1] == (None, False)

    shell.do_read("2026-07-01 include-private")
    assert calls[-1] == (date(2026, 7, 1), True)
