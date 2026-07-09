"""A minimal built-in journaling editor, offered as an alternative to external $EDITOR
commands. Distraction-free, with a live word count and goal indicator -- and unlike the
external-editor path, the text never touches disk in plaintext; it's held in memory and
handed straight back to the caller for encryption.

Built on Textual, which renders through its own terminal protocol handling (not `curses`,
which is POSIX-only), so this runs unchanged on Windows, WSL/Linux, and macOS -- the only
requirement is a terminal that understands ANSI/VT escape sequences, which every mainstream
terminal on all three platforms does.
"""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass
from datetime import date

from textual.app import App, ComposeResult
from textual.widgets import Footer, Static, TextArea

from journ.words import count_words


@dataclass
class EditorResult:
    text: str
    private: bool


class JournEditorApp(App):
    # Textual binds ctrl+p to its command palette by default, which would swallow our
    # private-toggle binding below -- not needed in this minimal, distraction-free editor.
    ENABLE_COMMAND_PALETTE = False

    CSS = """
    TextArea {
        height: 1fr;
    }
    #status {
        height: 1;
        padding: 0 1;
        background: $panel;
    }
    #status.goal-met {
        background: $success;
        color: $text;
    }
    """

    BINDINGS = [
        ("ctrl+s", "save", "Save & exit"),
        ("escape", "cancel", "Discard & exit"),
        ("ctrl+p", "toggle_private", "Toggle private"),
    ]

    def __init__(
        self,
        initial_text: str,
        writing_goal: int,
        initial_private: bool = False,
        entry_date: date | None = None,
    ):
        super().__init__()
        self.initial_text = initial_text
        self.writing_goal = writing_goal
        self.is_private = initial_private
        self.entry_date = entry_date
        self.result: EditorResult | None = None

    def compose(self) -> ComposeResult:
        yield Static(self._status_text(count_words(self.initial_text)), id="status")
        yield TextArea(self.initial_text, id="entry", soft_wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        text_area = self.query_one("#entry", TextArea)
        text_area.focus()
        # Cursor otherwise defaults to the document start, which would silently interleave
        # new typing into the middle of an existing entry instead of appending to it.
        text_area.cursor_location = text_area.document.end
        self.query_one("#status", Static).set_class(
            count_words(self.initial_text) >= self.writing_goal, "goal-met"
        )

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        word_count = count_words(event.text_area.text)
        status = self.query_one("#status", Static)
        status.update(self._status_text(word_count))
        status.set_class(word_count >= self.writing_goal, "goal-met")

    def _status_text(self, word_count: int) -> str:
        state = "goal met" if word_count >= self.writing_goal else "in progress"
        private_segment = " -- \U0001f512 PRIVATE (ctrl+p to toggle)" if self.is_private else ""
        date_segment = f"Editing {self.entry_date.isoformat()} -- " if self.entry_date else ""
        return f"{date_segment}{word_count} / {self.writing_goal} words -- {state}{private_segment}"

    def action_save(self) -> None:
        self.result = EditorResult(
            text=self.query_one("#entry", TextArea).text, private=self.is_private
        )
        self.exit()

    def action_cancel(self) -> None:
        self.result = None
        self.exit()

    def action_toggle_private(self) -> None:
        self.is_private = not self.is_private
        text_area = self.query_one("#entry", TextArea)
        status = self.query_one("#status", Static)
        status.update(self._status_text(count_words(text_area.text)))


_STD_INPUT_HANDLE = -10


def _drain_pending_console_input() -> None:
    """Windows-only: Textual's raw-mode console session (or the getpass passphrase prompt
    before it) can leave a stray input record sitting in the console's input buffer once it
    exits -- msvcrt.kbhit()/getch() only see legacy "character ready" events and can miss
    other record types (e.g. a key-up record), so this uses the Win32 FlushConsoleInputBuffer
    API instead, which unconditionally discards every pending record regardless of type. If
    nothing is drained here, pyreadline3 -- which the (journ) shell prompt uses for
    readline-style editing on Windows -- can pick up a leftover record on the next input()
    call and misinterpret it as its own forward-i-search binding, dropping the user into an
    i-search prompt instead of the next (journ) prompt."""
    if os.name != "nt":
        return
    handle = ctypes.windll.kernel32.GetStdHandle(_STD_INPUT_HANDLE)
    ctypes.windll.kernel32.FlushConsoleInputBuffer(handle)


def run_builtin_editor(
    initial_text: str,
    writing_goal: int,
    initial_private: bool = False,
    entry_date: date | None = None,
) -> EditorResult | None:
    """Run the built-in editor and return the saved text/private state, or None if discarded.
    entry_date is shown in the status bar when set (used when editing a past day, so it's
    never mistaken for today's entry); write_today_entry leaves it unset since "today" needs
    no clarification."""
    app = JournEditorApp(initial_text, writing_goal, initial_private, entry_date)
    app.run()
    _drain_pending_console_input()
    return app.result
