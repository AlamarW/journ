import contextlib
import sys
from datetime import date

from textual.widgets import OptionList, Static

from journ import actions, browse, config
from journ.builtin_editor import EditorResult
from journ.models import JournalEntry


def _entry(entry_date, text, private=False):
    return JournalEntry(
        entry_date=entry_date,
        content=text.encode("utf-8"),
        is_encrypted=False,
        words_per_minute=None,
        accomplished_goal=False,
        updated_at="x",
        word_count=len(text.split()),
        private=private,
    )


def _visible_text(app) -> str:
    return str(app.query_one("#entry-text", Static).visual)


def _fake_suspend_using(stdout, stderr):
    # The real App.suspend() redirects stdout/stderr to the true console streams while
    # suspended, since Textual's App replaces sys.stdout with its own capture object while
    # running -- edit_entry's prints need an equivalent redirect here. Using whatever
    # stdout/stderr were live *before* run_test() started (pytest's own capture) rather than
    # sys.__stdout__ avoids depending on the real console's encoding, which the test
    # environment doesn't control.
    @contextlib.contextmanager
    def _fake_suspend():
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            yield

    return _fake_suspend


def test_adjacent_entry_date_steps_forward_and_backward():
    dates = [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)]
    assert browse.adjacent_entry_date(dates, date(2026, 7, 2), 1) == date(2026, 7, 3)
    assert browse.adjacent_entry_date(dates, date(2026, 7, 2), -1) == date(2026, 7, 1)


def test_adjacent_entry_date_returns_none_past_either_boundary():
    dates = [date(2026, 7, 1), date(2026, 7, 2)]
    assert browse.adjacent_entry_date(dates, date(2026, 7, 2), 1) is None
    assert browse.adjacent_entry_date(dates, date(2026, 7, 1), -1) is None


def test_adjacent_entry_date_returns_none_for_unknown_date():
    dates = [date(2026, 7, 1)]
    assert browse.adjacent_entry_date(dates, date(2099, 1, 1), 1) is None


def test_browse_entries_reports_empty_journal_without_launching_app(db, monkeypatch, capsys):
    db.create_profile(writing_goal=750)

    def _forbid(*args, **kwargs):
        raise AssertionError("BrowseApp should not be constructed for an empty journal")

    monkeypatch.setattr(browse, "BrowseApp", _forbid)

    browse.browse_entries(db)

    assert "No entries yet" in capsys.readouterr().out


async def test_list_shows_entries_newest_first_and_opens_detail_on_select(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "first entry"))
    db.upsert_entry(_entry(date(2026, 7, 3), "third entry"))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None)
    async with app.run_test() as pilot:
        option_list = app.query_one("#entry-list", OptionList)
        assert option_list.option_count == 2
        assert "2026-07-03" in str(option_list.get_option_at_index(0).prompt)
        assert "2026-07-01" in str(option_list.get_option_at_index(1).prompt)

        await pilot.press("down")
        await pilot.press("enter")
        await pilot.pause()

        assert app.mode == "detail"
        assert app.current_date == date(2026, 7, 3)
        assert "third entry" in _visible_text(app)


async def test_next_and_prev_navigate_and_hit_boundaries(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "day one"))
    db.upsert_entry(_entry(date(2026, 7, 2), "day two"))
    db.upsert_entry(_entry(date(2026, 7, 3), "day three"))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None, start_date=date(2026, 7, 1))
    async with app.run_test() as pilot:
        assert app.current_date == date(2026, 7, 1)

        await pilot.press("n")
        await pilot.pause()
        assert app.current_date == date(2026, 7, 2)

        await pilot.press("down")
        await pilot.pause()
        assert app.current_date == date(2026, 7, 3)

        await pilot.press("down")
        await pilot.pause()
        assert app.current_date == date(2026, 7, 3)
        assert any("most recent" in n.message for n in app._notifications)

        await pilot.press("p")
        await pilot.press("up")
        await pilot.press("up")
        await pilot.pause()
        assert app.current_date == date(2026, 7, 1)
        assert any("earliest" in n.message for n in app._notifications)


async def test_vim_keys_navigate_the_list_cursor(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "first entry"))
    db.upsert_entry(_entry(date(2026, 7, 3), "third entry"))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None)
    async with app.run_test() as pilot:
        option_list = app.query_one("#entry-list", OptionList)
        assert option_list.highlighted is None

        await pilot.press("j")
        await pilot.pause()
        assert option_list.highlighted == 0

        await pilot.press("j")
        await pilot.pause()
        assert option_list.highlighted == 1

        await pilot.press("k")
        await pilot.pause()
        assert option_list.highlighted == 0


async def test_vim_keys_step_next_and_prev_in_detail_view(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "day one"))
    db.upsert_entry(_entry(date(2026, 7, 2), "day two"))
    db.upsert_entry(_entry(date(2026, 7, 3), "day three"))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None, start_date=date(2026, 7, 1))
    async with app.run_test() as pilot:
        await pilot.press("j")
        await pilot.pause()
        assert app.current_date == date(2026, 7, 2)

        await pilot.press("k")
        await pilot.pause()
        assert app.current_date == date(2026, 7, 1)

        await pilot.press("l")
        await pilot.pause()
        assert app.current_date == date(2026, 7, 2)

        await pilot.press("h")
        await pilot.pause()
        assert app.current_date == date(2026, 7, 1)


async def test_footer_shows_next_prev_list_edit_hints_in_detail_view(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "an entry"))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None, start_date=date(2026, 7, 1))
    async with app.run_test(size=(100, 24)) as pilot:
        await pilot.pause(0.1)
        footer_text = app.export_screenshot(simplify=True)
        for label in ("Next", "Prev", "List", "Edit", "Quit"):
            assert label in footer_text


async def test_list_command_returns_to_list_view(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "day one"))
    db.upsert_entry(_entry(date(2026, 7, 2), "day two"))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None, start_date=date(2026, 7, 1))
    async with app.run_test() as pilot:
        assert app.mode == "detail"

        await pilot.press("b")
        await pilot.pause()

        assert app.mode == "list"
        option_list = app.query_one("#entry-list", OptionList)
        assert option_list.option_count == 2


async def test_edit_hands_off_and_redisplays_updated_entry(db, monkeypatch):
    db.create_profile(writing_goal=1)
    past = date(2026, 7, 1)
    db.upsert_entry(_entry(past, "original text"))
    profile = db.get_profile()
    monkeypatch.setattr(actions.config, "get_editor", lambda: config.BUILTIN_EDITOR)
    monkeypatch.setattr(
        actions,
        "run_builtin_editor",
        lambda text, goal, priv=False, entry_date=None: EditorResult(
            text="edited text", private=priv
        ),
    )

    app = browse.BrowseApp(db, profile, key=None, start_date=past)
    monkeypatch.setattr(app, "suspend", _fake_suspend_using(sys.stdout, sys.stderr))

    async with app.run_test() as pilot:
        await pilot.press("e")
        await pilot.pause()

        assert app.mode == "detail"
        assert "edited text" in _visible_text(app)
        assert db.get_entry(past).content.decode("utf-8") == "edited text"


async def test_excludes_private_entries_by_default(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "public entry"))
    db.upsert_entry(_entry(date(2026, 7, 2), "secret entry", private=True))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None)
    async with app.run_test():
        option_list = app.query_one("#entry-list", OptionList)
        assert option_list.option_count == 1
        assert "2026-07-01" in str(option_list.get_option_at_index(0).prompt)


async def test_include_private_shows_private_entries(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "public entry"))
    db.upsert_entry(_entry(date(2026, 7, 2), "secret entry", private=True))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None, include_private=True)
    async with app.run_test():
        option_list = app.query_one("#entry-list", OptionList)
        assert option_list.option_count == 2


async def test_unknown_start_date_stays_at_list_with_notification(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "only entry"))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None, start_date=date(2099, 1, 1))
    async with app.run_test():
        assert app.mode == "list"
        assert any("No entry on that date" in n.message for n in app._notifications)


async def test_quit_exits_the_app(db):
    db.create_profile(writing_goal=750)
    db.upsert_entry(_entry(date(2026, 7, 1), "an entry"))
    profile = db.get_profile()

    app = browse.BrowseApp(db, profile, key=None)
    async with app.run_test() as pilot:
        await pilot.press("q")
        await pilot.pause()
        assert app._exit is True
