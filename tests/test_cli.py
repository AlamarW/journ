import sys
from datetime import date, timedelta

from typer.testing import CliRunner

from journ import cli, config

runner = CliRunner()


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "journ_config_dir", tmp_path / ".journ")
    monkeypatch.setattr(config, "journal_filepath", tmp_path / ".journ" / "journal.db")
    monkeypatch.setattr(config, "journ_tmp_dir", tmp_path / ".journ" / "tmp")
    monkeypatch.setattr(config, "editor_config_filepath", tmp_path / ".journ" / "editor.cfg")
    monkeypatch.setenv("EDITOR", f"{sys.executable} {STUB_EDITOR}")


def _write_stub_editor(tmp_path):
    stub = tmp_path / "stub_editor.py"
    stub.write_text(
        "import sys\n"
        "with open(sys.argv[1], 'a', encoding='utf-8') as f:\n"
        "    f.write('a solid handful of words written by the stub editor today')\n"
    )
    return stub


def test_write_then_stats_and_streak(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)

    # first-run profile setup: goal, then decline passphrase
    result = runner.invoke(cli.app, ["write"], input="5\nn\n")
    assert result.exit_code == 0, result.output
    assert "over your goal" in result.output

    result = runner.invoke(cli.app, ["stats"])
    assert result.exit_code == 0, result.output
    assert "Total words written" in result.output

    result = runner.invoke(cli.app, ["streak"])
    assert result.exit_code == 0, result.output
    assert "Streak: 1 day" in result.output


def test_goal_show_and_set(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)

    result = runner.invoke(cli.app, ["goal"], input="750\nn\n")
    assert result.exit_code == 0, result.output
    assert "750" in result.output

    result = runner.invoke(cli.app, ["goal", "1000"])
    assert result.exit_code == 0, result.output
    assert "1000" in result.output


def test_stats_output_has_no_raw_ansi_codes_when_piped(tmp_path, monkeypatch):
    # CliRunner captures output as a non-TTY stream; rich.Console must auto-detect that and
    # skip styling, so scripted/piped use of one-shot commands stays clean, parseable text.
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)

    runner.invoke(cli.app, ["write"], input="5\nn\n")
    result = runner.invoke(cli.app, ["stats"])

    assert "\x1b[" not in result.output


def test_editor_show_then_set_builtin(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "journ_config_dir", tmp_path / ".journ")
    monkeypatch.setattr(config, "editor_config_filepath", tmp_path / ".journ" / "editor.cfg")
    monkeypatch.delenv("EDITOR", raising=False)
    # "Currently using" wording is platform-dependent (see actions.manage_editor); pin it
    # so this test is deterministic regardless of which OS actually runs it in CI.
    monkeypatch.setattr(config.os, "name", "posix")

    result = runner.invoke(cli.app, ["editor"])
    assert result.exit_code == 0, result.output
    assert "nano" in result.output

    result = runner.invoke(cli.app, ["editor", "set"], input="1\n")
    assert result.exit_code == 0, result.output
    assert "built-in editor" in result.output
    assert (tmp_path / ".journ" / "editor.cfg").read_text() == config.BUILTIN_EDITOR

    result = runner.invoke(cli.app, ["editor"])
    assert result.exit_code == 0, result.output
    assert "built-in editor" in result.output


def test_metadata_analytics_commands_smoke(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)

    result = runner.invoke(cli.app, ["write"], input="5\nn\n")
    assert result.exit_code == 0, result.output

    for command in (
        ["calendar"],
        ["trends"],
        ["trends", "--days", "7"],
        ["records"],
        ["patterns"],
        ["suggest"],
    ):
        result = runner.invoke(cli.app, command)
        assert result.exit_code == 0, (command, result.output)


def test_content_commands_smoke_on_unencrypted_journal(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)

    runner.invoke(cli.app, ["write"], input="5\nn\n")

    result = runner.invoke(cli.app, ["frequency"])
    assert result.exit_code == 0, result.output
    assert "stub" in result.output  # from the stub editor's fixed text

    result = runner.invoke(cli.app, ["search", "stub"])
    assert result.exit_code == 0, result.output
    assert "matched" in result.output

    result = runner.invoke(cli.app, ["search", "nonexistent-phrase-xyz"])
    assert result.exit_code == 0, result.output
    assert "No entries matched" in result.output

    result = runner.invoke(cli.app, ["on-this-day"])
    assert result.exit_code == 0, result.output

    export_path = tmp_path / "export.json"
    result = runner.invoke(cli.app, ["export", str(export_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert export_path.exists()
    assert "stub" in export_path.read_text()


def test_export_rejects_unknown_format(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)
    runner.invoke(cli.app, ["write"], input="5\nn\n")

    result = runner.invoke(cli.app, ["export", str(tmp_path / "out.txt"), "--format", "xml"])
    assert result.exit_code == 0, result.output
    assert "must be" in result.output.lower()
    assert not (tmp_path / "out.txt").exists()


def test_export_include_private_flag(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)
    runner.invoke(cli.app, ["write", "--private"], input="5\nn\n")

    export_path = tmp_path / "export.json"
    result = runner.invoke(cli.app, ["export", str(export_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    assert "--include-private" in result.output
    assert not export_path.exists()

    result = runner.invoke(
        cli.app, ["export", str(export_path), "--format", "json", "--include-private"]
    )
    assert result.exit_code == 0, result.output
    assert export_path.exists()
    assert "stub" in export_path.read_text()


def test_write_private_flag_marks_new_entry_private(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)

    result = runner.invoke(cli.app, ["write", "--private"], input="5\nn\n")
    assert result.exit_code == 0, result.output

    result = runner.invoke(cli.app, ["private", date.today().isoformat(), "--unset"])
    assert "no longer private" in result.output  # confirms it *was* private beforehand


def test_write_rejects_both_private_and_unprivate(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    result = runner.invoke(cli.app, ["write", "--private", "--unprivate"])
    assert result.exit_code == 1
    assert "can't both be set" in result.output


def test_private_command_marks_and_unmarks_entry(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)
    runner.invoke(cli.app, ["write"], input="5\nn\n")

    today = date.today().isoformat()

    result = runner.invoke(cli.app, ["private", today])
    assert result.exit_code == 0, result.output
    assert "now private" in result.output

    result = runner.invoke(cli.app, ["private", today, "--unset"])
    assert result.exit_code == 0, result.output
    assert "no longer private" in result.output


def test_edit_command_backfills_past_day_and_prints_date_banner(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)
    runner.invoke(cli.app, ["write"], input="5\nn\n")  # first-run profile setup

    past = (date.today() - timedelta(days=2)).isoformat()
    result = runner.invoke(cli.app, ["edit", past])

    assert result.exit_code == 0, result.output
    assert f"Editing entry for {past}" in result.output
    assert "Backfilled entry" in result.output


def test_edit_command_rejects_editing_today(tmp_path, monkeypatch):
    global STUB_EDITOR
    STUB_EDITOR = _write_stub_editor(tmp_path)
    _isolate(tmp_path, monkeypatch)
    runner.invoke(cli.app, ["write"], input="5\nn\n")

    result = runner.invoke(cli.app, ["edit", date.today().isoformat()])

    assert result.exit_code == 0, result.output
    assert "Use `write`" in result.output


def test_read_command_parses_date_and_include_private_flag(tmp_path, monkeypatch):
    # browse_entries launches a full-screen Textual app, which can't be driven through
    # CliRunner's stdin simulation (Textual reads raw terminal bytes via its own driver, not
    # input()) -- so this only verifies the CLI layer parses arguments and calls through,
    # the same boundary the built-in editor's CLI wiring is tested at (see _isolate always
    # pointing EDITOR at an external stub rather than exercising the Textual editor here).
    _isolate(tmp_path, monkeypatch)
    calls = []
    monkeypatch.setattr(
        cli.browse,
        "browse_entries",
        lambda db, start_date=None, include_private=False: calls.append(
            (start_date, include_private)
        ),
    )

    result = runner.invoke(cli.app, ["read"])
    assert result.exit_code == 0, result.output
    assert calls[-1] == (None, False)

    today = date.today()
    result = runner.invoke(cli.app, ["read", today.isoformat(), "--include-private"])
    assert result.exit_code == 0, result.output
    assert calls[-1] == (today, True)


def test_mcp_unlock_status_lock_flow(tmp_path, monkeypatch, fake_keyring):
    _isolate(tmp_path, monkeypatch)
    # First-run profile setup with a passphrase this time.
    runner.invoke(cli.app, ["goal"], input="750\ny\nhunter2\nhunter2\n")

    result = runner.invoke(cli.app, ["mcp", "status"])
    assert result.exit_code == 0, result.output
    assert "No key is currently cached" in result.output

    result = runner.invoke(cli.app, ["mcp", "unlock"], input="hunter2\n")
    assert result.exit_code == 0, result.output
    assert "cached indefinitely" in result.output

    result = runner.invoke(cli.app, ["mcp", "status"])
    assert result.exit_code == 0, result.output
    assert "has been cached for" in result.output

    result = runner.invoke(cli.app, ["mcp", "lock"])
    assert result.exit_code == 0, result.output
    assert "removed" in result.output

    result = runner.invoke(cli.app, ["mcp", "status"])
    assert "No key is currently cached" in result.output


def test_mcp_serve_private_without_content_errors(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    runner.invoke(cli.app, ["goal"], input="750\nn\n")

    result = runner.invoke(cli.app, ["mcp", "serve", "--private"])
    assert result.exit_code == 1
    assert "--private requires --content" in result.output
