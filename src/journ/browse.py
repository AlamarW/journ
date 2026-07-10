"""Interactive, cursor-navigable browsing of past entries. Built on Textual for the same
reason builtin_editor.py is: arrow-key/terminal input handled by Textual's own driver rather
than hand-rolled raw console reads, which have been a repeated source of Windows-only bugs
in this codebase.

A single flat App (rather than Textual's Screen push/pop stack) toggles between a list view
and a detail view by showing/hiding two always-mounted widgets -- Screen stacking hit an
internal Textual rendering crash when popping back to a resumed screen in this version, so
this sidesteps that entirely.
"""

from __future__ import annotations

from datetime import date

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, OptionList, Static
from textual.widgets.option_list import Option

from journ import actions
from journ.db import Database
from journ.models import Profile


class _EntryText(Static):
    # Static isn't focusable by default -- without this, focus silently stays on the (hidden)
    # OptionList in detail mode, which then intercepts up/down for its own cursor instead of
    # letting them bubble up to the App's next/prev bindings.
    can_focus = True


def adjacent_entry_date(dates: list[date], current: date, step: int) -> date | None:
    """Pure next/prev lookup over an already-sorted, already-filtered list of dates. Returns
    None if `current` isn't in the list, or stepping would go past either end."""
    try:
        index = dates.index(current) + step
    except ValueError:
        return None
    if 0 <= index < len(dates):
        return dates[index]
    return None


class BrowseApp(App):
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("q", "quit_browse", "Quit"),
        Binding("escape", "escape_pressed", "Back/Quit", show=False),
        Binding("n", "next", "Next", show=False),
        Binding("down", "next", "Next", show=False),
        Binding("p", "prev", "Prev", show=False),
        Binding("up", "prev", "Prev", show=False),
        Binding("l", "back_to_list", "List", show=False),
        Binding("e", "edit", "Edit", show=False),
    ]

    CSS = """
    #entry-text {
        border: round $primary;
        height: 1fr;
        padding: 1 2;
    }
    """

    def __init__(
        self,
        db: Database,
        profile: Profile,
        key: bytes | None,
        start_date: date | None = None,
        include_private: bool = False,
    ) -> None:
        super().__init__()
        self.db = db
        self.profile = profile
        self.key = key
        self.include_private = include_private
        self.start_date = start_date
        self.entries: list = []
        self.dates: list[date] = []
        self.mode = "list"
        self.current_date: date | None = None

    def compose(self) -> ComposeResult:
        yield OptionList(id="entry-list")
        yield _EntryText(id="entry-text")
        yield Footer()

    def on_mount(self) -> None:
        self.refresh_entries()
        self.query_one("#entry-text", Static).display = False
        self._show_list()
        if self.start_date is not None:
            if self.start_date in self.dates:
                self._show_detail(self.start_date)
            else:
                self.notify("No entry on that date.")

    def refresh_entries(self) -> None:
        self.entries = actions.filter_private(self.db.all_entries(), self.include_private)
        self.dates = [e.entry_date for e in self.entries]

    def adjacent_date(self, current: date, step: int) -> date | None:
        return adjacent_entry_date(self.dates, current, step)

    def _show_list(self) -> None:
        self.mode = "list"
        option_list = self.query_one("#entry-list", OptionList)
        option_list.clear_options()
        for entry in reversed(self.entries):
            words = entry.word_count if entry.word_count is not None else "-"
            iso_date = entry.entry_date.isoformat()
            option_list.add_option(Option(f"{iso_date}   {words} words", id=iso_date))
        option_list.display = True
        self.query_one("#entry-text", Static).display = False
        option_list.focus()

    def _show_detail(self, entry_date: date) -> None:
        decrypted = actions.get_entry_by_date(
            self.db, self.profile, self.key, entry_date, include_private=self.include_private
        )
        if decrypted is None:
            self._show_list()
            return
        self.current_date = entry_date
        self.mode = "detail"
        text_widget = self.query_one("#entry-text", Static)
        text_widget.update(decrypted.text)
        text_widget.border_title = entry_date.isoformat()
        text_widget.display = True
        self.query_one("#entry-list", OptionList).display = False
        text_widget.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        assert event.option_id is not None
        self._show_detail(date.fromisoformat(event.option_id))

    def action_next(self) -> None:
        if self.mode != "detail" or self.current_date is None:
            return
        nxt = self.adjacent_date(self.current_date, 1)
        if nxt is None:
            self.notify("Already at the most recent entry.")
        else:
            self._show_detail(nxt)

    def action_prev(self) -> None:
        if self.mode != "detail" or self.current_date is None:
            return
        prv = self.adjacent_date(self.current_date, -1)
        if prv is None:
            self.notify("Already at the earliest entry.")
        else:
            self._show_detail(prv)

    def action_back_to_list(self) -> None:
        if self.mode == "detail":
            self._show_list()

    def action_escape_pressed(self) -> None:
        if self.mode == "detail":
            self._show_list()
        else:
            self.action_quit_browse()

    def action_edit(self) -> None:
        if self.mode != "detail" or self.current_date is None:
            return
        with self.suspend():
            actions.edit_entry(self.db, self.current_date, private=None)
        self.refresh_entries()
        self._show_detail(self.current_date)

    def action_quit_browse(self) -> None:
        self.exit()


def browse_entries(
    db: Database, start_date: date | None = None, include_private: bool = False
) -> None:
    """Read-only browse: a cursor-navigable list of every entry (date + word count), and a
    detail view for one entry at a time with next/prev/list/edit/quit navigation. `edit`
    suspends this app and hands off to the existing edit_entry verb unchanged, then resumes
    and re-renders whatever's on screen."""
    profile, key = actions.ensure_profile(db)
    if key is None:
        key = actions.unlock(profile)

    entries = actions.filter_private(db.all_entries(), include_private)
    if not entries:
        print("No entries yet. Write one with `write`.")
        return

    app = BrowseApp(db, profile, key, start_date=start_date, include_private=include_private)
    app.run()
