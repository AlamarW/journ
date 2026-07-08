"""Shared Rich console and print helpers.

Used by actions.py, so styling is applied once and shared identically between the
interactive REPL and the one-shot CLI subcommands. rich.Console auto-detects non-TTY output
(pipes, redirects) and strips styling automatically, so scripted/piped use of the one-shot
commands still gets clean, parseable plain text.
"""

from __future__ import annotations

from datetime import timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

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
    # zip() without strict= for py3.9 compatibility -- _PEN and _BANNER_BOX are both
    # fixed-length constants above, so length mismatch isn't a real runtime risk.
    lines = [pen.ljust(pen_width) + "  " + box for pen, box in zip(_PEN, _BANNER_BOX)]
    lines[1] = lines[1].replace("journ", "[bold cyan]journ[/bold cyan]")
    lines[2] = lines[2].replace("a terminal journal", "[dim]a terminal journal[/dim]")
    console.print("\n".join(lines))
    console.print(
        "Type [bold]help[/bold] or [bold]?[/bold] to list commands. "
        "Type [bold cyan]write[/bold cyan] to start.\n"
    )


def print_write_summary(
    *,
    word_count: int,
    writing_goal: int,
    goal_met: bool,
    elapsed: timedelta,
    words_per_minute: float,
    streak: int,
    streak_changed: bool,
    skip_goal_line: bool = False,
) -> None:
    from journ.words import format_elapsed

    lines = []
    if not skip_goal_line:
        if goal_met:
            lines.append(
                f"[bold green]✓[/bold green] {word_count} words -- over your goal of "
                f"{writing_goal}!"
            )
        else:
            lines.append(
                f"[bold yellow]○[/bold yellow] {word_count} words -- under your goal of "
                f"{writing_goal}"
            )
    lines.append(f"Journalled for {format_elapsed(elapsed)}, {words_per_minute} words/minute")
    if streak_changed:
        lines.append(f"[bold cyan]Streak is now {streak} day(s)![/bold cyan]")
    else:
        lines.append(f"Current streak: {streak} day(s)")

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
