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
from datetime import date

from textual.app import App, ComposeResult
from textual.binding import Binding
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
    #status.confirm {
        background: $error;
        color: $text;
    }
    """

    # ctrl+s is deliberately avoided -- on Windows it collides with pyreadline3's
    # forward-i-search binding for the (journ) shell prompt (and often the terminal's own
    # readline emulation too), which can leave the next prompt stuck in an i-search state
    # after saving. ctrl+shift+s doesn't work as a substitute: Textual's Windows driver reads
    # the console's translated character for a key event, and Windows translates ctrl+s and
    # ctrl+shift+s to the same control character, so they're indistinguishable on this stack.
    # ctrl+w ("write") saves instead. TextArea already binds plain ctrl+w to delete-word-left,
    # and non-priority bindings are checked from the focused widget upward, so TextArea would
    # claim it first without priority=True, which checks this binding from the App down before
    # the focused widget gets a turn. ctrl+q is repurposed to also discard-and-exit (same as
    # escape) rather than Textual's default quit-without-confirming -- it isn't claimed by
    # TextArea at all, but priority=True is kept for consistency with the original quit binding
    # it replaces.
    BINDINGS = [
        Binding("ctrl+w", "save", "Save & exit", priority=True),
        Binding("ctrl+q", "cancel", "Discard & exit", priority=True),
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
        self._confirm_discard = False

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
        self._confirm_discard = False
        word_count = count_words(event.text_area.text)
        status = self.query_one("#status", Static)
        status.update(self._status_text(word_count))
        status.set_class(word_count >= self.writing_goal, "goal-met")
        status.set_class(False, "confirm")

    def _status_text(self, word_count: int) -> str:
        state = "goal met" if word_count >= self.writing_goal else "in progress"
        private_segment = " | PRIVATE (ctrl+p to toggle)" if self.is_private else ""
        date_segment = f"Editing {self.entry_date.isoformat()} | " if self.entry_date else ""
        return f"{date_segment}{word_count} / {self.writing_goal} words | {state}{private_segment}"

    def action_save(self) -> None:
        self.result = EditorResult(
            text=self.query_one("#entry", TextArea).text, private=self.is_private
        )
        self.exit()

    def action_cancel(self) -> None:
        """Discard & exit -- but discarding UNSAVED CHANGES takes a second confirming
        press: ctrl+q sits right next to ctrl+w, and one mistyped discard once cost a
        real 600-word session (in stet, journ's sibling, which inherited this editor).
        A clean editor still exits on the first press. Any deliberate action in between
        (typing, toggling private, saving) cancels the pending discard. ctrl+q must stay
        bound regardless: Textual's own default for it is quit-without-confirming."""
        text = self.query_one("#entry", TextArea).text
        if text == self.initial_text or self._confirm_discard:
            self.result = None
            self.exit()
            return
        self._confirm_discard = True
        status = self.query_one("#status", Static)
        status.update("Unsaved changes -- press again to discard, ctrl+w to save")
        status.set_class(False, "goal-met")
        status.set_class(True, "confirm")

    def action_toggle_private(self) -> None:
        self.is_private = not self.is_private
        self._confirm_discard = False
        text_area = self.query_one("#entry", TextArea)
        word_count = count_words(text_area.text)
        status = self.query_one("#status", Static)
        status.update(self._status_text(word_count))
        status.set_class(word_count >= self.writing_goal, "goal-met")
        status.set_class(False, "confirm")


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
    return app.result
