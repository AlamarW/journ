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

from textual.app import App, ComposeResult
from textual.widgets import Footer, Static, TextArea

from journ.words import count_words


class JournEditorApp(App):
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
    ]

    def __init__(self, initial_text: str, writing_goal: int):
        super().__init__()
        self.initial_text = initial_text
        self.writing_goal = writing_goal
        self.result: str | None = None

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
        return f"{word_count} / {self.writing_goal} words -- {state}"

    def action_save(self) -> None:
        self.result = self.query_one("#entry", TextArea).text
        self.exit()

    def action_cancel(self) -> None:
        self.result = None
        self.exit()


def run_builtin_editor(initial_text: str, writing_goal: int) -> str | None:
    """Run the built-in editor and return the saved text, or None if discarded."""
    app = JournEditorApp(initial_text, writing_goal)
    app.run()
    return app.result
