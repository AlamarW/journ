"""Interactive list/detail loop for read-only browsing of past entries. Split out from
actions.py the same way builtin_editor.py splits out the write/edit editor loop -- keeps this
multi-turn prompt loop separate from the single-shot verbs in actions.py, which is already the
largest module in the codebase.
"""

from __future__ import annotations

from datetime import date

from journ import actions, ui
from journ.db import Database


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


def _browsable_entries(db: Database, include_private: bool):
    # db.all_entries() is already sorted ascending by entry_date -- keep that order so
    # adjacent_entry_date's step=+1 means "chronologically next" throughout.
    return actions.filter_private(db.all_entries(), include_private)


def browse_entries(
    db: Database, start_date: date | None = None, include_private: bool = False
) -> None:
    """Read-only browse: a list view of every entry (date + word count), and a detail view
    for one entry at a time with next/prev/list/edit/quit navigation. `edit` hands off to the
    existing edit_entry verb unchanged, then this loop re-displays whatever's on screen."""
    profile, key = actions.ensure_profile(db)
    if key is None:
        key = actions.unlock(profile)

    entries = _browsable_entries(db, include_private)
    dates = [e.entry_date for e in entries]
    if not dates:
        print("No entries yet. Write one with `write`.")
        return

    current: date | None = None
    mode = "list"
    if start_date is not None:
        if start_date in dates:
            current = start_date
            mode = "detail"
        else:
            print("No entry on that date.")

    try:
        while True:
            if mode == "list":
                ui.print_entry_list(list(reversed(entries)))
                choice = input("Enter a date to read, or 'q' to quit -> ").strip().lower()
                if choice in ("", "q", "quit"):
                    return
                try:
                    picked = date.fromisoformat(choice)
                except ValueError:
                    print("Date must be in YYYY-MM-DD format.")
                    continue
                if picked not in dates:
                    print("No entry on that date.")
                    continue
                current = picked
                mode = "detail"
                continue

            decrypted = actions.get_entry_by_date(
                db, profile, key, current, include_private=include_private
            )
            if decrypted is None:
                print("This entry is no longer visible with the current filters.")
                mode = "list"
                continue
            ui.print_browse_entry(decrypted)

            action = input("[n]ext  [p]rev  [l]ist  [e]dit  [q]uit -> ").strip().lower()
            if action in ("q", "quit"):
                return
            elif action == "":
                continue
            elif action in ("n", "next"):
                nxt = adjacent_entry_date(dates, current, 1)
                if nxt is None:
                    print("Already at the most recent entry.")
                else:
                    current = nxt
            elif action in ("p", "prev"):
                prv = adjacent_entry_date(dates, current, -1)
                if prv is None:
                    print("Already at the earliest entry.")
                else:
                    current = prv
            elif action in ("l", "list"):
                mode = "list"
            elif action in ("e", "edit"):
                actions.edit_entry(db, current, private=None)
                entries = _browsable_entries(db, include_private)
                dates = [e.entry_date for e in entries]
                if current not in dates:
                    print("This entry is no longer visible with the current filters.")
                    mode = "list"
            else:
                print("Unknown command. Use n, p, l, e, or q.")
    except (EOFError, KeyboardInterrupt):
        print()
        return
