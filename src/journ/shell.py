"""The interactive `(journ)` REPL -- kept as the default experience for users who like
staying in a persistent shell. Every command here just calls into actions.py so there's a
single implementation shared with the one-shot CLI subcommands in cli.py.
"""

from __future__ import annotations

import cmd
from typing import Callable

from journ import actions
from journ.actions import PassphraseError
from journ.db import Database
from journ.terminal import clear_screen


class JournalingShell(cmd.Cmd):
    intro = "Welcome to Journ, type help or ? to list commands\nType 'write' to start\n"
    prompt = "(journ) "

    def __init__(self, db: Database):
        super().__init__()
        self.db = db

    def _run(self, action_fn: Callable[[], None]) -> None:
        try:
            action_fn()
        except PassphraseError as exc:
            print(str(exc))

    def do_write(self, line):
        "Write today's journal entry in your text editor"
        self._run(lambda: actions.write_today_entry(self.db))

    do_journ = do_write  # backward-compatible alias for the old command name

    def do_streak(self, line):
        "Show your current streak"
        self._run(lambda: actions.show_streak(self.db))

    def do_last(self, line):
        "Show the word count of your most recent entry"
        self._run(lambda: actions.show_last_entry(self.db))

    def do_stats(self, line):
        "Show your average words-per-minute and total words written"
        self._run(lambda: actions.show_stats(self.db))

    def do_goal(self, line):
        "Show or set your daily writing goal: 'goal' or 'goal 750'"
        new_goal = None
        if line.strip():
            try:
                new_goal = int(line.strip())
            except ValueError:
                print("Goal must be a whole number.")
                return
        self._run(lambda: actions.set_goal(self.db, new_goal))

    def do_passphrase(self, line):
        "Manage your passphrase: 'passphrase set|change|remove'"
        action_name = line.strip().lower()
        if action_name not in ("set", "change", "remove"):
            print("Usage: passphrase set|change|remove")
            return
        self._run(lambda: actions.manage_passphrase(self.db, action_name))

    def do_clear(self, line):
        "Clear the screen"
        clear_screen()

    def do_exit(self, line):
        "Exit journ"
        return True

    do_EOF = do_exit
