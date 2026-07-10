"""Shared Rich console and print helpers.

Used by actions.py, so styling is applied once and shared identically between the
interactive REPL and the one-shot CLI subcommands. rich.Console auto-detects non-TTY output
(pipes, redirects) and strips styling automatically, so scripted/piped use of the one-shot
commands still gets clean, parseable plain text.
"""

from __future__ import annotations

from datetime import date, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from journ import analytics
from journ.content import DecryptedEntry

console = Console()

_DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Verified for exact column alignment -- see the banner box math in _BANNER below.
_PEN = [
    "   ,/",
    "  //",
    " //",
    "//__",
]
_BANNER_BOX = [
    "+----------------------+",
    "|        journ         |",
    "|  a terminal journal  |",
    "+----------------------+",
]


def print_welcome() -> None:
    # _PEN rows are ragged (that's intentional -- it's a little pen doodle, not a
    # rectangle), so left-pad them to a common width before joining or the box columns
    # drift out of alignment row to row.
    pen_width = max(len(line) for line in _PEN)
    lines = [pen.ljust(pen_width) + "  " + box for pen, box in zip(_PEN, _BANNER_BOX, strict=True)]
    lines[1] = lines[1].replace("journ", "[bold cyan]journ[/bold cyan]")
    lines[2] = lines[2].replace("a terminal journal", "[dim]a terminal journal[/dim]")
    console.print("\n".join(lines))
    console.print(
        "Type [bold]help[/bold] or [bold]?[/bold] to list commands. "
        "Type [bold cyan]write[/bold cyan] to start.\n"
    )


def _format_milestone(kind: str, threshold: int) -> str:
    if kind == "words":
        label = f"{threshold:,} total words"
    elif kind == "entries":
        label = f"{threshold} entries"
    elif kind == "streak":
        label = f"{threshold}-day streak"
    else:
        label = f"{kind} {threshold}"
    return f"[bold magenta]\U0001f389 Milestone: {label}![/bold magenta]"


def print_write_summary(
    *,
    word_count: int,
    writing_goal: int,
    goal_met: bool,
    elapsed: timedelta,
    words_per_minute: float,
    streak: int,
    streak_changed: bool,
    milestones: list[tuple[str, int]] = (),
    private: bool = False,
) -> None:
    from journ.words import format_elapsed

    lines = []
    if goal_met:
        lines.append(
            f"[bold green]✓[/bold green] {word_count} words -- over your goal of {writing_goal}!"
        )
    else:
        lines.append(
            f"[bold yellow]○[/bold yellow] {word_count} words -- under your goal of {writing_goal}"
        )
    lines.append(f"Journalled for {format_elapsed(elapsed)}, {words_per_minute} words/minute")
    if streak_changed:
        lines.append(f"[bold cyan]Streak is now {streak} day(s)![/bold cyan]")
    else:
        lines.append(f"Current streak: {streak} day(s)")

    for kind, threshold in milestones:
        lines.append(_format_milestone(kind, threshold))

    if private:
        lines.append("[dim]Saved as a private entry.[/dim]")

    console.print(Panel("\n".join(lines), title="journ", title_align="left", border_style="cyan"))


def print_edit_summary(
    *,
    entry_date: date,
    is_new_entry: bool,
    word_count: int,
    writing_goal: int,
    goal_met: bool,
    streak: int,
    streak_changed: bool,
    milestones: list[tuple[str, int]] = (),
    private: bool = False,
) -> None:
    action = "Backfilled" if is_new_entry else "Edited"
    lines = [f"{action} entry for {entry_date.isoformat()}"]
    if goal_met:
        lines.append(
            f"[bold green]✓[/bold green] {word_count} words -- over your goal of {writing_goal}!"
        )
    else:
        lines.append(
            f"[bold yellow]○[/bold yellow] {word_count} words -- under your goal of {writing_goal}"
        )

    if streak_changed:
        lines.append(f"[bold cyan]Streak is now {streak} day(s)![/bold cyan]")
    else:
        lines.append(f"Current streak: {streak} day(s)")

    for kind, threshold in milestones:
        lines.append(_format_milestone(kind, threshold))

    if private:
        lines.append("[dim]Saved as a private entry.[/dim]")

    console.print(Panel("\n".join(lines), title="journ", title_align="left", border_style="cyan"))


def print_stats_table(*, avg_wpm: float, total_words: int, entry_count: int) -> None:
    table = Table(title="journ stats", title_justify="left")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Average words/minute", str(avg_wpm))
    table.add_row("Total words written", str(total_words))
    table.add_row("Entries", str(entry_count))
    console.print(table)


def print_streak_line(streak: int) -> None:
    if streak > 0:
        console.print(f"[bold cyan]\U0001f525 Streak: {streak} day(s)[/bold cyan]")
    else:
        console.print("No streak yet -- write today's entry to start one.")


def print_calendar(grid: list[list[analytics.CalendarDay]], consistency: float) -> None:
    if not grid:
        console.print("Not enough data yet.")
        return

    lines = []
    for row in range(7):
        cells = []
        for week in grid:
            day = week[row]
            cells.append("[green]■[/green]" if day.wrote else "[dim]·[/dim]")
        lines.append(f"{_DAY_LABELS[row]}  " + "".join(cells))
    console.print("\n".join(lines))
    console.print(f"\nConsistency (last 30 days): {consistency:.0%}")


def print_trends(points: list[analytics.TrendPoint]) -> None:
    if not points:
        console.print("Not enough data yet.")
        return

    values = [p.word_count for p in points]
    goal_days = sum(1 for p in points if p.goal_met)
    console.print(f"Last {len(points)} days: {analytics.sparkline(values)}")
    console.print(f"Goal met on {goal_days}/{len(points)} days")

    written_days = [v for v in values if v > 0]
    if written_days:
        average = round(sum(written_days) / len(written_days))
        console.print(f"Average on writing days: {average} words")


def print_records(records: analytics.Records | None) -> None:
    if records is None:
        console.print("Not enough data yet for records.")
        return

    table = Table(title="Personal records", title_justify="left")
    table.add_column("Record")
    table.add_column("Value", justify="right")
    table.add_row(
        "Longest entry",
        f"{records.longest_entry_words} words ({records.longest_entry_date.isoformat()})",
    )
    if records.best_wpm_date:
        table.add_row(
            "Best words/minute",
            f"{records.best_wpm_value} ({records.best_wpm_date.isoformat()})",
        )
    table.add_row("Current streak", f"{records.current_streak} day(s)")
    table.add_row("Longest streak ever", f"{records.longest_streak} day(s)")
    console.print(table)


def print_patterns(pattern: analytics.PatternSummary) -> None:
    if not any(pattern.by_day_of_week.values()):
        console.print(
            "Not enough data yet -- writing-pattern insights only cover entries "
            "written since this feature was added."
        )
        return

    console.print("[bold]Writing patterns[/bold]\n")

    by_day = Table(title="By day of week", title_justify="left")
    by_day.add_column("Day")
    by_day.add_column("Entries", justify="right")
    for day, count in pattern.by_day_of_week.items():
        by_day.add_row(day, str(count))
    console.print(by_day)

    by_time = Table(title="By time of day", title_justify="left")
    by_time.add_column("Time")
    by_time.add_column("Entries", justify="right")
    for band, count in pattern.by_time_of_day.items():
        by_time.add_row(band, str(count))
    console.print(by_time)


def print_word_frequency(freq: list[tuple[str, int]]) -> None:
    if not freq:
        console.print("No words to show yet.")
        return

    table = Table(title="Most-used words", title_justify="left")
    table.add_column("Word")
    table.add_column("Count", justify="right")
    for word, count in freq:
        table.add_row(word, str(count))
    console.print(table)


def print_search_results(query: str, results: list[tuple]) -> None:
    if not results:
        console.print(f"No entries matched '{query}'.")
        return

    console.print(f"[bold]{len(results)}[/bold] entries matched '{query}':\n")
    for entry_date, snippet in results:
        console.print(f"[cyan]{entry_date.isoformat()}[/cyan]  {snippet}")


def print_on_this_day(entries: list[DecryptedEntry]) -> None:
    if not entries:
        console.print("No entries from this day in previous years yet.")
        return
    for entry in sorted(entries, key=lambda e: e.entry_date):
        console.print(
            Panel(
                entry.text,
                title=entry.entry_date.isoformat(),
                title_align="left",
                border_style="cyan",
            )
        )


def print_goal_suggestion(*, current_goal: int, suggested: int | None) -> None:
    if suggested is None:
        console.print(
            f"Your current goal ({current_goal} words) already fits your recent writing well."
        )
        return
    direction = "up" if suggested > current_goal else "down"
    console.print(
        f"Based on your recent entries, consider adjusting your goal {direction} from "
        f"{current_goal} to [bold]{suggested}[/bold] words. Run `journ goal {suggested}` "
        "to apply it."
    )


def print_repl_help(groups: list[tuple[str, list[tuple[str, str]]]]) -> None:
    table = Table(title="journ commands", title_justify="left")
    table.add_column("Command", style="bold cyan", no_wrap=True)
    table.add_column("Description")

    for index, (section, commands) in enumerate(groups):
        table.add_row(f"[bold]{section}[/bold]", "")
        for name, description in commands:
            table.add_row(f"  {name}", description)
        if index < len(groups) - 1:
            table.add_section()

    console.print(table)
    console.print("\nType [bold]help <command>[/bold] for more detail on a specific command.")
