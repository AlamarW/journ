"""MCP server exposing journ's data to LLM clients over stdio.

Tier 1 (metadata, always registered): calendar, trends, records, patterns, suggest-goal,
streak, goal, stats-totals -- all zero-decryption, backed by db.all_entries()/get_profile()
plus analytics.py.

Tier 2 (content read+write, only registered when content=True): search, word-frequency,
on-this-day, recent-entries, get-entry-by-date, save-conversation-entry. Gated by not even
calling add_tool for these when content=False, so a client without content access never sees
they exist.

Tier 3 (private, private=True): modifies Tier-2 read tool behavior (include_private=True);
does not add or remove any tools.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import date, datetime
from typing import Any

from mcp.server.fastmcp import FastMCP

from journ import actions, mcp_keychain
from journ.actions import ConversationTurn
from journ.db import Database


class MCPStartupError(Exception):
    """Raised when the server can't safely start (e.g. --content requested but no cached key)."""


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    raise TypeError(f"Not JSON serializable: {obj!r}")


def _to_serializable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_serializable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_to_serializable(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _to_serializable(v) for k, v in obj.items()}
    return obj


def _to_json(obj: Any) -> str:
    return json.dumps(_to_serializable(obj), default=_json_default, indent=2)


def _resolve_content_key(db: Database, content: bool) -> bytes | None:
    """Resolves the key Tier-2 tools should use. Never prompts interactively -- stdin is
    reserved for the MCP JSON-RPC transport. Raises MCPStartupError instead of falling back
    to input()/getpass() when a key is required but unavailable."""
    if not content:
        return None
    profile = db.get_profile()
    if profile is None or not profile.has_passphrase:
        return None  # unencrypted journal (or no profile yet) -- Tier 2 works with key=None
    key = mcp_keychain.get_cached_key()
    if key is None:
        raise MCPStartupError(
            "This journal has a passphrase set but no key is cached. Run `journ mcp unlock` "
            "first, then retry `journ mcp serve --content`."
        )
    return key


def build_server(db: Database, content: bool, private: bool) -> FastMCP:
    key = _resolve_content_key(db, content)
    server = FastMCP(name="journ")

    _register_tier1_tools(server, db)
    if content:
        _register_tier2_tools(server, db, key, include_private=private)

    return server


def run_server(db: Database, content: bool, private: bool) -> None:
    server = build_server(db, content=content, private=private)
    server.run(transport="stdio")


# --- Tier 1: metadata-only, zero decryption ---


def _register_tier1_tools(server: FastMCP, db: Database) -> None:
    def get_calendar(weeks: int = 12) -> str:
        """Weekly heatmap of which days have an entry, plus 30-day consistency."""
        grid, score = actions.get_calendar_data(db, weeks=weeks)
        return _to_json({"weeks": grid, "consistency": score})

    def get_trends(days: int = 30) -> str:
        """Daily word-count / goal-completion trend for the last N days."""
        return _to_json(actions.get_trends_data(db, days))

    def get_records() -> str:
        """Personal records: longest entry, best words-per-minute, longest streak ever."""
        return _to_json(actions.get_records_data(db))

    def get_patterns() -> str:
        """When entries tend to be written: by day of week and time of day."""
        return _to_json(actions.get_patterns_data(db))

    def get_goal_suggestion() -> str:
        """Suggested daily word-count goal based on recent writing, if different from current."""
        current, suggested = actions.get_goal_suggestion(db)
        return _to_json({"current_goal": current, "suggested_goal": suggested})

    def get_streak() -> str:
        """Current and longest-ever writing streak, in days."""
        streak, longest_streak = actions.get_streak_data(db)
        return _to_json({"streak": streak, "longest_streak": longest_streak})

    def get_goal() -> str:
        """Current daily writing goal, in words."""
        return _to_json({"writing_goal": actions.get_current_goal(db)})

    def get_stats_totals() -> str:
        """Total words written, total entries, and average words-per-minute."""
        return _to_json(actions.get_stats_totals(db))

    for fn, name in [
        (get_calendar, "get_calendar"),
        (get_trends, "get_trends"),
        (get_records, "get_records"),
        (get_patterns, "get_patterns"),
        (get_goal_suggestion, "get_goal_suggestion"),
        (get_streak, "get_streak"),
        (get_goal, "get_goal"),
        (get_stats_totals, "get_stats_totals"),
    ]:
        server.add_tool(fn, name=name)


# --- Tier 2: content read + write, only registered when --content is passed ---


def _register_tier2_tools(
    server: FastMCP, db: Database, key: bytes | None, include_private: bool
) -> None:
    profile = db.get_profile()

    def search_journal(query: str) -> str:
        """Case-insensitive substring search across all (visible) entries; one snippet each."""
        entries = actions.filter_private(db.all_entries(), include_private)
        results = actions.get_search_results(db, profile, key, query, entries=entries)
        return _to_json([{"date": d, "snippet": s} for d, s in results])

    def get_word_frequency(top_n: int = 20) -> str:
        """Most-used words across all (visible) entries, stopwords excluded."""
        entries = actions.filter_private(db.all_entries(), include_private)
        return _to_json(
            actions.get_word_frequency(db, profile, key, entries=entries, top_n=top_n)
        )

    def get_on_this_day() -> str:
        """Entries written on today's month/day in previous years (visible ones only)."""
        entries = actions.filter_private(db.all_entries(), include_private)
        matches = actions.on_this_day_matches(entries)
        return _to_json(actions.get_on_this_day(db, profile, key, entries=matches))

    def get_recent_entries(n: int = 5) -> str:
        """The N most recently written visible entries, newest first."""
        entries = actions.filter_private(db.all_entries(), include_private)
        return _to_json(actions.get_recent_entries(db, profile, key, n=n, entries=entries))

    def get_entry_by_date(entry_date: str) -> str:
        """Full decrypted text of the entry for a given ISO date (YYYY-MM-DD), if it exists
        and is visible. Returns null if there's no entry, or if it's flagged private and
        --private wasn't enabled for this server."""
        parsed = date.fromisoformat(entry_date)
        entry = actions.get_entry_by_date(
            db, profile, key, parsed, include_private=include_private
        )
        return _to_json(entry) if entry else _to_json(None)

    def save_conversation_entry(
        entry_date: str, turns: list[dict], private: bool | None = None
    ) -> str:
        """Saves/appends this conversation (both user and assistant turns) as a journal entry
        for the given ISO date (YYYY-MM-DD). Only the user's own words count toward
        word_count/goal/streak. `turns` is a list of {"role": "user"|"assistant", "text": str}.
        Streak is only updated when entry_date is today -- saving a past conversation won't
        affect your streak. Pass private=true/false to explicitly set the entry's private flag;
        omit it to leave the flag as-is (defaults to not private for a brand-new entry)."""
        parsed_date = date.fromisoformat(entry_date)
        parsed_turns = [ConversationTurn(role=t["role"], text=t["text"]) for t in turns]
        result = actions.save_conversation_entry(
            db, parsed_date, parsed_turns, key, private=private
        )
        return _to_json(result)

    for fn, name in [
        (search_journal, "search_journal"),
        (get_word_frequency, "get_word_frequency"),
        (get_on_this_day, "get_on_this_day"),
        (get_recent_entries, "get_recent_entries"),
        (get_entry_by_date, "get_entry_by_date"),
        (save_conversation_entry, "save_conversation_entry"),
    ]:
        server.add_tool(fn, name=name)
