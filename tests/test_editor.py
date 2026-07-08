import io

import pytest

from journ import config


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".journ"
    monkeypatch.setattr(config, "journ_config_dir", config_dir)
    monkeypatch.setattr(config, "editor_config_filepath", config_dir / "editor.cfg")
    return config_dir


def test_editor_env_var_takes_priority(monkeypatch, isolated_config):
    monkeypatch.setenv("EDITOR", "vim")
    assert config.get_editor() == "vim"


def test_saved_editor_used_when_no_env_var(monkeypatch, isolated_config):
    monkeypatch.delenv("EDITOR", raising=False)
    isolated_config.mkdir(parents=True)
    (isolated_config / "editor.cfg").write_text("emacs")
    assert config.get_editor() == "emacs"


def test_posix_default_is_nano(monkeypatch, isolated_config):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(config.os, "name", "posix")
    assert config.get_editor() == "nano"


def test_windows_picker_selects_and_saves_notepad(monkeypatch, isolated_config):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(config.os, "name", "nt")
    monkeypatch.setattr(config.shutil, "which", lambda exe: None)
    monkeypatch.setattr("sys.stdin", io.StringIO("1\n"))

    chosen = config.get_editor()

    assert chosen == "notepad"
    assert (isolated_config / "editor.cfg").read_text() == "notepad"


def test_windows_picker_reuses_saved_choice_without_prompting(monkeypatch, isolated_config):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(config.os, "name", "nt")
    isolated_config.mkdir(parents=True)
    (isolated_config / "editor.cfg").write_text("notepad")
    monkeypatch.setattr("sys.stdin", io.StringIO(""))  # would raise if input() were called

    assert config.get_editor() == "notepad"


def test_windows_picker_custom_command(monkeypatch, isolated_config):
    monkeypatch.delenv("EDITOR", raising=False)
    monkeypatch.setattr(config.os, "name", "nt")
    monkeypatch.setattr(config.shutil, "which", lambda exe: None)
    # Only notepad is "available" (always true), so option 2 is "custom command".
    monkeypatch.setattr("sys.stdin", io.StringIO("2\ncode --wait\n"))

    assert config.get_editor() == "code --wait"


def test_editor_argv_posix_split(monkeypatch):
    monkeypatch.setattr(config.os, "name", "posix")
    assert config.editor_argv("code --wait") == ["code", "--wait"]


def test_editor_argv_windows_strips_quotes_and_keeps_backslashes(monkeypatch):
    monkeypatch.setattr(config.os, "name", "nt")
    argv = config.editor_argv('"C:\\Program Files\\Notepad++\\notepad++.exe" -multiInst')
    assert argv == ["C:\\Program Files\\Notepad++\\notepad++.exe", "-multiInst"]
