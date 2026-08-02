"""journ's config is a thin delegation to quire.config.

The resolution rules ($EDITOR precedence, the Windows picker, argv splitting) are tested in
quire against its own EditorEnvironment. What remains journ's responsibility is that the
delegation hands quire journ's own name and paths, that the path globals stay
monkeypatchable, and that the re-exports the rest of journ imports are actually there.
"""

import pytest
from quire.config import EditorEnvironment

from journ import config


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".journ"
    monkeypatch.setattr(config, "journ_config_dir", config_dir)
    monkeypatch.setattr(config, "editor_config_filepath", config_dir / "editor.cfg")
    monkeypatch.delenv("EDITOR", raising=False)
    return config_dir


class TestDelegation:
    def test_choice_roundtrips_through_journs_own_paths(self, isolated_config):
        """Also proves the environment is rebuilt per call -- one captured at import would
        have written to the real ~/.journ before the fixture patched these globals."""
        config.save_editor_choice("code --wait")

        written = (isolated_config / "editor.cfg").read_text(encoding="utf-8")
        assert written == "code --wait"
        assert config.read_saved_editor() == "code --wait"
        assert config.get_editor() == "code --wait"

    def test_env_var_wins(self, isolated_config, monkeypatch):
        monkeypatch.setenv("EDITOR", "vim")
        config.save_editor_choice("notepad")
        assert config.get_editor() == "vim"

    def test_saved_editor_used_when_no_env_var(self, isolated_config):
        isolated_config.mkdir(parents=True)
        (isolated_config / "editor.cfg").write_text("emacs")
        assert config.get_editor() == "emacs"


class TestBuiltinEditorSentinel:
    def test_journs_literal_matches_what_quire_derives(self):
        """journ keeps the literal because it is what is already saved in users' editor.cfg;
        quire derives the same string from the app name. They must not drift apart."""
        derived = EditorEnvironment(
            app_name="journ",
            config_dir=config.journ_config_dir,
            editor_config_filepath=config.editor_config_filepath,
        ).builtin_editor
        assert config.BUILTIN_EDITOR == derived


class TestReExports:
    def test_editor_argv_is_reachable_from_journ_config(self):
        """actions.py calls config.editor_argv; the re-export is load-bearing."""
        assert config.editor_argv("code --wait") == ["code", "--wait"]
