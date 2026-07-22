"""journ's command-line entry point.

Bare `journ` opens the interactive (journ) shell, exactly like before. The subcommands
below are scriptable one-shot equivalents of the same actions, useful for aliases, status
bars, or scripting -- they share their implementation with the shell via actions.py.
"""

from datetime import date
from pathlib import Path

import typer

from journ import actions, browse, config, ui
from journ.actions import PassphraseError
from journ.db import Database
from journ.shell import JournalingShell
from journ.terminal import clear_screen

app = typer.Typer(
    help="A terminal journaling tool that honors your text editor of choice.",
    no_args_is_help=False,
)

passphrase_app = typer.Typer(help="Manage the passphrase that encrypts your entries.")
app.add_typer(passphrase_app, name="passphrase")

editor_app = typer.Typer(help="Show or change the editor journ uses.")
app.add_typer(editor_app, name="editor")

mcp_app = typer.Typer(
    help=(
        "Run journ as an MCP server for LLM clients, and manage the cached key. "
        "Tier 1 (metadata/stats) is exposed by default; `serve --content` adds "
        "Tier 2 (read/write entry text), and `--private` extends Tier 2 to "
        "private entries."
    )
)
app.add_typer(mcp_app, name="mcp")


def _open_db() -> Database:
    return Database(config.journal_filepath)


def _run(action_fn) -> None:
    try:
        action_fn()
    except PassphraseError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


def _open_shell() -> None:
    ui.set_shell_mode(True)
    with _open_db() as db:
        clear_screen()
        actions.ensure_profile(db)
        clear_screen()
        ui.print_welcome()
        JournalingShell(db).cmdloop()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _open_shell()


@app.command()
def shell() -> None:
    """Open the interactive (journ) shell, the default when run with no subcommand."""
    _open_shell()


@app.command()
def write(
    private: bool = typer.Option(
        False,
        "--private",
        help="Mark today's entry private (initial state for the built-in editor).",
    ),
    unprivate: bool = typer.Option(
        False, "--unprivate", help="Clear today's entry's private flag."
    ),
) -> None:
    """Write today's journal entry in your text editor."""
    if private and unprivate:
        typer.echo("--private and --unprivate can't both be set.")
        raise typer.Exit(code=1)
    resolved_private = True if private else (False if unprivate else None)
    with _open_db() as db:
        _run(lambda: actions.write_today_entry(db, private=resolved_private))


@app.command()
def edit(
    entry_date: str = typer.Argument(..., help="ISO date (YYYY-MM-DD) of the entry to edit."),
    private: bool = typer.Option(
        False, "--private", help="Mark the entry private (initial state for the built-in editor)."
    ),
    unprivate: bool = typer.Option(False, "--unprivate", help="Clear the entry's private flag."),
) -> None:
    """Edit (or backfill) a past day's entry in your text editor."""
    if private and unprivate:
        typer.echo("--private and --unprivate can't both be set.")
        raise typer.Exit(code=1)
    resolved_private = True if private else (False if unprivate else None)
    with _open_db() as db:
        _run(
            lambda: actions.edit_entry(db, date.fromisoformat(entry_date), private=resolved_private)
        )


@app.command()
def read(
    entry_date: str = typer.Argument(
        None, help="ISO date (YYYY-MM-DD) to jump straight to. Omit to start from the list."
    ),
    include_private: bool = typer.Option(
        False, "--include-private", help="Include entries flagged private while browsing."
    ),
) -> None:
    """Browse past entries: a list view, step through with next/prev, or edit from within."""
    start_date = date.fromisoformat(entry_date) if entry_date else None
    with _open_db() as db:
        _run(
            lambda: browse.browse_entries(
                db, start_date=start_date, include_private=include_private
            )
        )


@app.command()
def stats() -> None:
    """Show your average words-per-minute and total words written."""
    with _open_db() as db:
        _run(lambda: actions.show_stats(db))


@app.command()
def streak() -> None:
    """Show your current streak."""
    with _open_db() as db:
        _run(lambda: actions.show_streak(db))


@app.command()
def last() -> None:
    """Show the word count of your most recent entry."""
    with _open_db() as db:
        _run(lambda: actions.show_last_entry(db))


@app.command()
def goal(new_goal: int | None = typer.Argument(None)) -> None:
    """Show or set your daily writing goal."""
    with _open_db() as db:
        _run(lambda: actions.set_goal(db, new_goal))


@app.command()
def calendar() -> None:
    """Show a heatmap of which days you've written, and your 30-day consistency."""
    with _open_db() as db:
        _run(lambda: actions.show_calendar(db))


@app.command()
def trends(days: int = typer.Option(30, "--days", help="How many days back to show.")) -> None:
    """Show word count / goal-completion trends over recent days."""
    with _open_db() as db:
        _run(lambda: actions.show_trends(db, days))


@app.command()
def records() -> None:
    """Show personal records: longest entry, best words-per-minute, longest streak ever."""
    with _open_db() as db:
        _run(lambda: actions.show_records(db))


@app.command()
def patterns() -> None:
    """Show when you tend to write: by day of week and time of day."""
    with _open_db() as db:
        _run(lambda: actions.show_patterns(db))


@app.command()
def suggest() -> None:
    """Suggest a daily writing goal based on your recent entries."""
    with _open_db() as db:
        _run(lambda: actions.suggest_goal_action(db))


@app.command()
def frequency() -> None:
    """Show your most-used words across all entries."""
    with _open_db() as db:
        _run(lambda: actions.show_word_frequency(db))


@app.command()
def search(query: str) -> None:
    """Search your entries for a word or phrase."""
    with _open_db() as db:
        _run(lambda: actions.search_journal(db, query))


@app.command(name="on-this-day")
def on_this_day() -> None:
    """Show entries written on this date in previous years."""
    with _open_db() as db:
        _run(lambda: actions.show_on_this_day(db))


@app.command()
def private(
    entry_date: str = typer.Argument(..., help="ISO date (YYYY-MM-DD) of the entry to flag."),
    unset: bool = typer.Option(
        False, "--unset", help="Remove the private flag instead of setting it."
    ),
) -> None:
    """Flag (or unflag) an entry as private, excluding it from MCP content tools by default."""
    with _open_db() as db:
        _run(lambda: actions.set_private(db, date.fromisoformat(entry_date), not unset))


@app.command()
def export(
    output_path: Path,
    export_format: str = typer.Option("md", "--format", help="'md' or 'json'."),
    include_private: bool = typer.Option(
        False, "--include-private", help="Include entries flagged private in the export."
    ),
) -> None:
    """Export all entries to a markdown or JSON file."""
    with _open_db() as db:
        _run(
            lambda: actions.export_journal(
                db, output_path, export_format, include_private=include_private
            )
        )


@editor_app.callback(invoke_without_command=True)
def editor_main(ctx: typer.Context) -> None:
    """Show the currently configured editor."""
    if ctx.invoked_subcommand is None:
        actions.manage_editor(reconfigure=False)


@editor_app.command("set")
def editor_set() -> None:
    """Interactively choose an editor, including journ's built-in one."""
    actions.manage_editor(reconfigure=True)


@passphrase_app.command("set")
def passphrase_set() -> None:
    """Set a passphrase for the first time."""
    with _open_db() as db:
        _run(lambda: actions.manage_passphrase(db, "set"))


@passphrase_app.command("change")
def passphrase_change() -> None:
    """Change your existing passphrase."""
    with _open_db() as db:
        _run(lambda: actions.manage_passphrase(db, "change"))


@passphrase_app.command("remove")
def passphrase_remove() -> None:
    """Remove your passphrase (entries are re-stored unencrypted)."""
    with _open_db() as db:
        _run(lambda: actions.manage_passphrase(db, "remove"))


@mcp_app.command("unlock")
def mcp_unlock() -> None:
    """Cache your derived passphrase key in the OS credential store, for
    `journ mcp serve --content`."""
    with _open_db() as db:
        _run(lambda: actions.mcp_unlock(db))


@mcp_app.command("lock")
def mcp_lock() -> None:
    """Remove the cached passphrase key from the OS credential store."""
    _run(actions.mcp_lock)


@mcp_app.command("status")
def mcp_status() -> None:
    """Show whether a passphrase key is currently cached for the MCP server."""
    _run(actions.mcp_status)


@mcp_app.command("serve")
def mcp_serve(
    content: bool = typer.Option(
        False,
        "--content",
        help=(
            "Expose Tier 2 tools that read/write entry text (search, read, save). "
            "Without this, only metadata/stats tools are available."
        ),
    ),
    mcp_private: bool = typer.Option(
        False,
        "--private",
        help=(
            "Also expose entries flagged private through Tier 2 tools. Requires "
            "--content; private entries are excluded otherwise."
        ),
    ),
) -> None:
    """Start journ's MCP server over stdio, for use with an MCP-capable LLM client.

    By default only Tier 1 metadata tools are exposed; use --content and --private
    to add more.
    """
    from journ.mcp_server import MCPStartupError, run_server

    if mcp_private and not content:
        typer.echo("--private requires --content.")
        raise typer.Exit(code=1)

    with _open_db() as db:
        try:
            run_server(db, content=content, private=mcp_private)
        except MCPStartupError as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
