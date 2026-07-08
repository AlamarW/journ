"""The interactive `(journ)` REPL -- kept as the default experience for users who like
staying in a persistent shell. Every command here just calls into actions.py so there's a
single implementation shared with the one-shot CLI subcommands in cli.py.
"""

from __future__ import annotations

import cmd
from collections.abc import Callable
from datetime import date
from pathlib import Path

from journ import actions, ui
from journ.actions import PassphraseError
from journ.db import Database
from journ.terminal import clear_screen

# Grouped for the custom `help` overview -- deliberately excludes the do_journ/do_EOF
# aliases, which exist for backward compatibility and Ctrl+D but would just be noise here.
_HELP_GROUPS = [
    ("Write", ["write", "private", "stats", "streak", "last", "goal"]),
    (
        "Analytics",
        [
            "calendar", "trends", "records", "patterns", "suggest", "frequency",
            "search", "on_this_day", "export",
        ],
    ),
    ("Configuration", ["editor", "passphrase"]),
    ("Shell", ["clear", "help", "exit"]),
]


class JournalingShell(cmd.Cmd):
    # Empty: the welcome banner is printed via ui.print_welcome() before cmdloop() starts
    # (see cli.py:_open_shell), so it renders identically for `journ` and `journ shell`.
    intro = ""
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
        "Write today's entry: 'write', 'write private', or 'write unprivate'"
        arg = line.strip().lower()
        if arg == "":
            private = None
        elif arg == "private":
            private = True
        elif arg == "unprivate":
            private = False
        else:
            print("Usage: write  |  write private  |  write unprivate")
            return
        self._run(lambda: actions.write_today_entry(self.db, private=private))

    do_journ = do_write  # backward-compatible alias for the old command name

    def do_private(self, line):
        "Flag or unflag an entry as private: 'private 2026-07-01' or 'private 2026-07-01 unset'"
        parts = line.strip().split()
        if not parts:
            print("Usage: private <date> [unset]")
            return
        try:
            entry_date = date.fromisoformat(parts[0])
        except ValueError:
            print("Date must be in YYYY-MM-DD format.")
            return
        unset = len(parts) > 1 and parts[1].lower() == "unset"
        self._run(lambda: actions.set_private(self.db, entry_date, not unset))

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

    def do_calendar(self, line):
        "Show a heatmap of which days you've written, and your 30-day consistency"
        self._run(lambda: actions.show_calendar(self.db))

    def do_trends(self, line):
        "Show word count / goal-completion trends: 'trends' or 'trends 60' (days back)"
        days = 30
        if line.strip():
            try:
                days = int(line.strip())
            except ValueError:
                print("Days must be a whole number.")
                return
        self._run(lambda: actions.show_trends(self.db, days))

    def do_records(self, line):
        "Show personal records: longest entry, best words-per-minute, longest streak ever"
        self._run(lambda: actions.show_records(self.db))

    def do_patterns(self, line):
        "Show when you tend to write: by day of week and time of day"
        self._run(lambda: actions.show_patterns(self.db))

    def do_suggest(self, line):
        "Suggest a daily writing goal based on your recent entries"
        self._run(lambda: actions.suggest_goal_action(self.db))

    def do_frequency(self, line):
        "Show your most-used words across all entries"
        self._run(lambda: actions.show_word_frequency(self.db))

    def do_search(self, line):
        "Search your entries for a word or phrase: 'search some phrase'"
        query = line.strip()
        if not query:
            print("Usage: search <word or phrase>")
            return
        self._run(lambda: actions.search_journal(self.db, query))

    def do_on_this_day(self, line):
        "Show entries written on this date in previous years"
        self._run(lambda: actions.show_on_this_day(self.db))

    def do_export(self, line):
        "Export all entries: 'export path/to/file.md' or 'export path/to/file.json'"
        parts = line.strip().split()
        if not parts:
            print("Usage: export <path> [md|json]")
            return
        output_path = Path(parts[0])
        export_format = parts[1] if len(parts) > 1 else "md"
        self._run(lambda: actions.export_journal(self.db, output_path, export_format))

    def do_editor(self, line):
        "Show or change your editor: 'editor' or 'editor set' (includes journ's built-in one)"
        arg = line.strip().lower()
        if arg not in ("", "set"):
            print("Usage: editor  |  editor set")
            return
        self._run(lambda: actions.manage_editor(reconfigure=(arg == "set")))

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

    def do_help(self, arg):
        "List all commands, or 'help <command>' for detail on a specific one"
        if arg:
            super().do_help(arg)
            return
        groups = [
            (section, [(name, getattr(self, f"do_{name}").__doc__ or "") for name in names])
            for section, names in _HELP_GROUPS
        ]
        ui.print_repl_help(groups)

    def do_exit(self, line):
        "Exit journ"
        return True

    do_EOF = do_exit
