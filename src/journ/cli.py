"""journ's command-line entry point.

Bare `journ` opens the interactive (journ) shell, exactly like before. The subcommands
below are scriptable one-shot equivalents of the same actions, useful for aliases, status
bars, or scripting -- they share their implementation with the shell via actions.py.
"""

from typing import Optional

import typer

from journ import actions, config
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


def _open_db() -> Database:
    return Database(config.journal_filepath)


def _run(action_fn) -> None:
    try:
        action_fn()
    except PassphraseError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


def _open_shell() -> None:
    with _open_db() as db:
        clear_screen()
        actions.ensure_profile(db)
        clear_screen()
        JournalingShell(db).cmdloop()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        _open_shell()


@app.command()
def shell() -> None:
    """Open the interactive (journ) shell -- the default when run with no subcommand."""
    _open_shell()


@app.command()
def write() -> None:
    """Write today's journal entry in your text editor."""
    with _open_db() as db:
        _run(lambda: actions.write_today_entry(db))


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
def goal(new_goal: Optional[int] = typer.Argument(None)) -> None:
    """Show or set your daily writing goal."""
    with _open_db() as db:
        _run(lambda: actions.set_goal(db, new_goal))


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


if __name__ == "__main__":
    app()
