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

from dataclasses import dataclass

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

    def __init__(self, initial_text: str, writing_goal: int, initial_private: bool = False):
        super().__init__()
        self.initial_text = initial_text
        self.writing_goal = writing_goal
        self.is_private = initial_private
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
        return f"{word_count} / {self.writing_goal} words -- {state}{private_segment}"

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


def run_builtin_editor(
    initial_text: str, writing_goal: int, initial_private: bool = False
) -> EditorResult | None:
    """Run the built-in editor and return the saved text/private state, or None if discarded."""
    app = JournEditorApp(initial_text, writing_goal, initial_private)
    app.run()
    return app.result
