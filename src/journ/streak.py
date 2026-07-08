"""Pure streak-calculation logic, decoupled from I/O so it's trivially testable.

Driven by comparing dates rather than a manually-toggled boolean flag, so re-editing
today's entry twice (or any other repeat call for the same day) can't double-increment
the streak -- the bug tracked in the old README's Bug List.
"""

from __future__ import annotations

from datetime import date, timedelta


def update_streak(
    current_streak: int,
    last_entry_date: date | None,
    today: date,
    goal_met: bool,
) -> tuple[int, date | None]:
    """Returns (new_streak, new_last_entry_date) after today's entry."""
    if not goal_met:
        return current_streak, last_entry_date

    if last_entry_date == today:
        return current_streak, last_entry_date

    if last_entry_date == today - timedelta(days=1):
        return current_streak + 1, today

    return 1, today
