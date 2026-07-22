"""Local paths and text-editor resolution."""

import os
import shlex
import shutil
from pathlib import Path

home_dir = Path.home()
journ_config_dir = home_dir / ".journ"
journal_filepath = journ_config_dir / "journal.db"
journ_tmp_dir = journ_config_dir / "tmp"
editor_config_filepath = journ_config_dir / "editor.cfg"

BUILTIN_EDITOR = "__journ_builtin__"

EDITOR_CHOICES = [
    (BUILTIN_EDITOR, "journ's built-in editor (distraction-free, live word count)"),
    ("notepad", "Notepad (built into Windows)"),
    ("code --wait", "Visual Studio Code"),
    ("notepad++", "Notepad++"),
    ("subl --wait", "Sublime Text"),
    ("vim", "Vim"),
]


def read_saved_editor() -> str | None:
    if editor_config_filepath.is_file():
        saved_editor = editor_config_filepath.read_text(encoding="utf-8").strip()
        if saved_editor:
            return saved_editor
    return None


def save_editor_choice(editor_command: str) -> None:
    journ_config_dir.mkdir(parents=True, exist_ok=True)
    editor_config_filepath.write_text(editor_command, encoding="utf-8")


def prompt_editor_choice() -> str:
    """Interactively pick an editor. Used both by the automatic Windows first-run prompt
    and by the explicit `journ editor set` command on any platform."""
    print("Pick a text editor for journ to use (this choice is saved for next time):\n")

    available_choices = []
    for command, label in EDITOR_CHOICES:
        executable = command.split(" ")[0]
        is_builtin = executable == BUILTIN_EDITOR
        is_notepad_on_windows = executable == "notepad" and os.name == "nt"
        if is_builtin or is_notepad_on_windows or shutil.which(executable):
            available_choices.append((command, label))

    for index, (command, label) in enumerate(available_choices, start=1):
        suffix = "" if command == BUILTIN_EDITOR else f"  ({command})"
        print(f"  {index}. {label}{suffix}")
    custom_choice_number = len(available_choices) + 1
    print(f"  {custom_choice_number}. Enter a custom command")

    while True:
        choice = input("Choice -> ").strip()
        try:
            choice_number = int(choice)
        except ValueError:
            print("Please enter a number")
            continue

        if 1 <= choice_number <= len(available_choices):
            return available_choices[choice_number - 1][0]
        elif choice_number == custom_choice_number:
            custom_command = input("Enter the editor command (e.g. 'code --wait') -> ").strip()
            if custom_command:
                return custom_command
        else:
            print("Invalid choice, try again")


def get_editor() -> str:
    """Resolve the text editor to use: EDITOR env var, saved choice, or (on Windows) a picker."""
    editor = os.getenv("EDITOR")
    if editor:
        return editor

    saved_editor = read_saved_editor()
    if saved_editor:
        return saved_editor

    from journ import ui  # local import: config stays importable without the Rich stack

    if os.name == "nt":
        print("No EDITOR environment variable is set.")
        chosen_editor = prompt_editor_choice()
        save_editor_choice(chosen_editor)
        label = "journ's built-in editor" if chosen_editor == BUILTIN_EDITOR else chosen_editor
        print(
            f"Using {label} going forward. Change it anytime with `{ui.cmd('editor set')}`, by "
            f"setting $env:EDITOR, or by deleting {editor_config_filepath}\n"
        )
        return chosen_editor

    print(
        "No EDITOR environment variable set, defaulting to 'nano'. Set EDITOR to use a "
        f"different editor, or run `{ui.cmd('editor set')}` to pick one (including journ's "
        "built-in editor)."
    )
    return "nano"


def editor_argv(editor: str) -> list[str]:
    """Split an EDITOR command string into argv, respecting platform quoting conventions."""
    is_windows = os.name == "nt"
    tokens = shlex.split(editor, posix=not is_windows)
    if is_windows:
        # shlex's non-posix mode (needed to preserve Windows path backslashes) does not
        # strip the quote characters it uses for tokenization, unlike posix mode.
        tokens = [t[1:-1] if len(t) >= 2 and t[0] == '"' and t[-1] == '"' else t for t in tokens]
    return tokens
