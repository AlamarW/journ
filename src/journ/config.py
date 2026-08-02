"""Local paths and text-editor resolution.

The resolution rules themselves live in `quire.config`, shared with stet. This module
supplies journ's name and paths and keeps the zero-argument signatures the rest of journ
already calls, so nothing outside here had to change.
"""

from pathlib import Path

from quire import config as _quire
from quire.config import EditorEnvironment, editor_argv  # noqa: F401  -- re-exported

home_dir = Path.home()
journ_config_dir = home_dir / ".journ"
journal_filepath = journ_config_dir / "journal.db"
journ_tmp_dir = journ_config_dir / "tmp"
# Recovery copies of discarded editor text. Deliberately NOT under journ_tmp_dir: the
# external-editor flow sweeps tmp/*.txt on every launch and would destroy them.
journ_discard_dir = journ_config_dir / "discarded"
editor_config_filepath = journ_config_dir / "editor.cfg"

BUILTIN_EDITOR = "__journ_builtin__"


def _cmd(text: str) -> str:
    from journ import ui  # local import: config stays importable without the Rich stack

    return ui.cmd(text)


def _env() -> EditorEnvironment:
    """Rebuilt on every call rather than cached at import, because the path globals above
    are monkeypatched by the test suite and by nothing else."""
    return EditorEnvironment(
        app_name="journ",
        config_dir=journ_config_dir,
        editor_config_filepath=editor_config_filepath,
        cmd=_cmd,
    )


def read_saved_editor() -> str | None:
    return _quire.read_saved_editor(_env())


def save_editor_choice(editor_command: str) -> None:
    _quire.save_editor_choice(_env(), editor_command)


def prompt_editor_choice() -> str:
    return _quire.prompt_editor_choice(_env())


def get_editor() -> str:
    return _quire.get_editor(_env())
