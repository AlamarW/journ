"""journ's built-in editor: quire's editor plus the two things that are journ's own -- a
footer showing progress against the writing goal, and ctrl+p to mark an entry private.

The layout, the save/discard keys, and the two-press discard confirmation all live in
quire.editor now, shared with stet.

The text still never touches disk in plaintext from here: quire hands it back in memory and
the caller decides what to do with it. A discarded entry is no longer thrown away, but what
gets written -- and whether it is encrypted first -- stays journ's decision, not quire's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from quire.editor import EditorApp, ExtraBinding, FooterText, build_editor
from quire.editor import EditorResult as QuireEditorResult


@dataclass
class EditorResult:
    text: str
    """The editor's final text, whether or not it was saved -- on a discard the caller can
    stash it (encrypted) for recovery instead of losing it."""
    private: bool
    saved: bool


class PrivateFlag:
    """The private toggle's state for one session. Held here rather than in quire because
    "private" is journ's concept; quire only knows to re-render after the key fires."""

    def __init__(self, private: bool):
        self.private = private

    def toggle(self) -> None:
        self.private = not self.private


def status_text(word_count: int, writing_goal: int, private: bool, entry_date: date | None) -> str:
    state = "goal met" if word_count >= writing_goal else "in progress"
    private_segment = " | PRIVATE (ctrl+p to toggle)" if private else ""
    date_segment = f"Editing {entry_date.isoformat()} | " if entry_date else ""
    return f"{date_segment}{word_count} / {writing_goal} words | {state}{private_segment}"


def build_journ_editor(
    initial_text: str,
    writing_goal: int,
    initial_private: bool = False,
    entry_date: date | None = None,
) -> tuple[EditorApp, PrivateFlag]:
    """Build the configured editor and the private-flag state it mutates, without running
    it. The test suite drives this with Textual's `run_test()` pilot."""
    flag = PrivateFlag(initial_private)

    def footer(word_count: int) -> FooterText:
        return FooterText(
            text=status_text(word_count, writing_goal, flag.private, entry_date),
            # quire's emphasis style is the success state; journ spends it on the goal.
            emphasis=word_count >= writing_goal,
        )

    private_binding = ExtraBinding(key="ctrl+p", description="Toggle private", action=flag.toggle)
    return build_editor(initial_text, footer, [private_binding]), flag


def run_builtin_editor(
    initial_text: str,
    writing_goal: int,
    initial_private: bool = False,
    entry_date: date | None = None,
) -> EditorResult:
    """Run the built-in editor. The result always carries the final text and private flag;
    `saved` says whether the user chose to keep it.

    entry_date is shown in the status bar when set (used when editing a past day, so it's
    never mistaken for today's entry); write_today_entry leaves it unset since "today" needs
    no clarification."""
    app, flag = build_journ_editor(initial_text, writing_goal, initial_private, entry_date)
    app.run()
    # app.result is None only if the app exited without either action (e.g. a crash);
    # treat that as an unsaved exit with the original text so nothing is ever lost.
    result = app.result or QuireEditorResult(text=initial_text, saved=False)
    return EditorResult(text=result.text, private=flag.private, saved=result.saved)
