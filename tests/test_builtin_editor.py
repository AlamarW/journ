from datetime import date

from journ.builtin_editor import JournEditorApp


async def test_save_appends_at_cursor_end_not_start():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*" more")
        await pilot.press("ctrl+w")
        await pilot.pause()

    assert app.result.text == "existing text more"
    assert app.result.private is False


async def test_escape_with_no_changes_exits_immediately():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


async def test_escape_with_changes_needs_a_second_press():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*"more")
        await pilot.press("escape")
        await pilot.pause()

        # First press warns and stays.
        status = app.query_one("#status")
        assert "Unsaved changes" in str(status.render())
        assert "confirm" in status.classes

        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


async def test_ctrl_q_shares_the_confirmation_with_escape():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*"more")
        await pilot.press("ctrl+q")
        await pilot.pause()
        assert "confirm" in app.query_one("#status").classes

        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


async def test_typing_cancels_pending_discard():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*"more")
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()

        status = app.query_one("#status")
        assert "Unsaved changes" not in str(status.render())
        assert "confirm" not in status.classes

        # A single escape must warn again rather than exit.
        await pilot.press("escape")
        await pilot.pause()
        assert app.result is None
        assert "confirm" in status.classes


async def test_private_toggle_cancels_pending_discard():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*"more")
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("ctrl+p")
        await pilot.pause()

        assert "confirm" not in app.query_one("#status").classes
        assert app.is_private is True


async def test_ctrl_w_saves_even_while_confirmation_pending():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*" more")
        await pilot.press("escape")
        await pilot.press("ctrl+w")
        await pilot.pause()

    assert app.result.text == "existing text more"


async def test_status_reflects_live_word_count_and_goal_state():
    app = JournEditorApp("", writing_goal=2)
    async with app.run_test() as pilot:
        status = app.query_one("#status")
        assert "goal-met" not in status.classes

        await pilot.press(*"hi there")
        await pilot.pause()
        assert "goal-met" in status.classes


async def test_ctrl_p_toggles_private_state():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        assert app.is_private is False

        await pilot.press("ctrl+p")
        await pilot.pause()
        assert app.is_private is True

        await pilot.press("ctrl+p")
        await pilot.pause()
        assert app.is_private is False


def test_status_text_includes_private_indicator_only_when_private():
    app = JournEditorApp("existing text", writing_goal=100)
    assert "PRIVATE" not in app._status_text(5)

    app.is_private = True
    assert "PRIVATE" in app._status_text(5)


def test_status_text_includes_entry_date_only_when_set():
    app = JournEditorApp("existing text", writing_goal=100)
    assert "Editing" not in app._status_text(5)

    dated_app = JournEditorApp("existing text", writing_goal=100, entry_date=date(2026, 7, 1))
    assert "Editing 2026-07-01" in dated_app._status_text(5)


async def test_save_reflects_private_state_at_save_time():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.press("ctrl+w")
        await pilot.pause()

    assert app.result.private is True


async def test_initial_private_true_carries_through_to_save():
    app = JournEditorApp("existing text", writing_goal=100, initial_private=True)
    async with app.run_test() as pilot:
        assert app.is_private is True
        assert "PRIVATE" in app._status_text(2)

        await pilot.press("ctrl+w")
        await pilot.pause()

    assert app.result.private is True
