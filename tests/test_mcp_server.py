import json
from datetime import date

import pytest

from journ import crypto, mcp_keychain, mcp_server
from journ.models import JournalEntry

_TIER1_TOOLS = {
    "get_calendar", "get_trends", "get_records", "get_patterns",
    "get_goal_suggestion", "get_streak", "get_goal", "get_stats_totals",
}
_TIER2_TOOLS = {
    "search_journal", "get_word_frequency", "get_on_this_day",
    "get_entry_by_date", "save_conversation_entry",
}


async def test_tier1_tools_registered_with_content_false(db):
    server = mcp_server.build_server(db, content=False, private=False)
    names = {t.name for t in await server.list_tools()}
    assert names == _TIER1_TOOLS


async def test_tier2_tools_registered_with_content_true(db):
    server = mcp_server.build_server(db, content=True, private=False)
    names = {t.name for t in await server.list_tools()}
    assert names == _TIER1_TOOLS | _TIER2_TOOLS


async def test_private_flag_does_not_change_tool_count(db):
    server_without = mcp_server.build_server(db, content=True, private=False)
    server_with = mcp_server.build_server(db, content=True, private=True)
    names_without = {t.name for t in await server_without.list_tools()}
    names_with = {t.name for t in await server_with.list_tools()}
    assert names_without == names_with


def test_startup_raises_when_content_requested_encrypted_no_cached_key(db, fake_keyring):
    db.create_profile(writing_goal=750)
    salt, canary = crypto.setup_passphrase("does-not-matter")
    db.set_passphrase(salt, canary)

    with pytest.raises(mcp_server.MCPStartupError):
        mcp_server.build_server(db, content=True, private=False)


def test_content_tools_work_with_no_passphrase_set_and_no_cached_key(db, fake_keyring):
    db.create_profile(writing_goal=750)
    # Should not raise -- no passphrase means Tier 2 works with key=None, same convention
    # used everywhere else in the codebase.
    server = mcp_server.build_server(db, content=True, private=False)
    assert server is not None


def test_content_tools_work_with_cached_key(db, fake_keyring):
    db.create_profile(writing_goal=750)
    passphrase = "correct horse battery staple"
    salt, canary = crypto.setup_passphrase(passphrase)
    key = crypto.derive_key(passphrase, salt)
    db.set_passphrase(salt, canary)
    mcp_keychain.cache_key(key)

    server = mcp_server.build_server(db, content=True, private=False)
    assert server is not None


def test_tier1_tools_work_on_brand_new_database_with_no_profile(db):
    server = mcp_server.build_server(db, content=False, private=False)
    assert server is not None


async def test_call_get_calendar_tool_end_to_end(db):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"x", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=5,
        )
    )
    server = mcp_server.build_server(db, content=False, private=False)

    content_blocks, _ = await server.call_tool("get_calendar", {})
    payload = json.loads(content_blocks[0].text)
    assert "weeks" in payload
    assert "consistency" in payload


async def test_call_search_journal_tool_end_to_end(db):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"wandering thoughts here", is_encrypted=False,
            words_per_minute=None, accomplished_goal=True, updated_at="x", word_count=3,
        )
    )
    server = mcp_server.build_server(db, content=True, private=False)

    content_blocks, _ = await server.call_tool("search_journal", {"query": "wandering"})
    payload = json.loads(content_blocks[0].text)
    assert payload[0]["date"] == "2026-07-01"
    assert "wandering" in payload[0]["snippet"]


async def test_call_save_conversation_entry_tool_mutates_db(db):
    db.create_profile(writing_goal=1)
    server = mcp_server.build_server(db, content=True, private=False)

    await server.call_tool(
        "save_conversation_entry",
        {
            "entry_date": date.today().isoformat(),
            "turns": [{"role": "user", "text": "three new words"}],
        },
    )

    entry = db.get_entry(date.today())
    assert entry is not None
    assert entry.word_count == 3


async def test_get_entry_by_date_tool_respects_private_flag(db):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"secret", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=1,
            private=True,
        )
    )

    server_no_private = mcp_server.build_server(db, content=True, private=False)
    content_blocks, _ = await server_no_private.call_tool(
        "get_entry_by_date", {"entry_date": "2026-07-01"}
    )
    assert json.loads(content_blocks[0].text) is None

    server_with_private = mcp_server.build_server(db, content=True, private=True)
    content_blocks, _ = await server_with_private.call_tool(
        "get_entry_by_date", {"entry_date": "2026-07-01"}
    )
    payload = json.loads(content_blocks[0].text)
    assert payload["text"] == "secret"


async def test_search_journal_excludes_private_entries_by_default(db):
    db.create_profile(writing_goal=1)
    db.upsert_entry(
        JournalEntry(
            entry_date=date(2026, 7, 1), content=b"a secret confession", is_encrypted=False,
            words_per_minute=None, accomplished_goal=False, updated_at="x", word_count=3,
            private=True,
        )
    )
    server = mcp_server.build_server(db, content=True, private=False)

    content_blocks, _ = await server.call_tool("search_journal", {"query": "secret"})
    payload = json.loads(content_blocks[0].text)
    assert payload == []
