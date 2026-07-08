import sys

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
    assert "total of" in result.output

    result = runner.invoke(cli.app, ["streak"])
    assert result.exit_code == 0, result.output
    assert "streak is currently 1" in result.output


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
