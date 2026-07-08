from journ.builtin_editor import JournEditorApp


async def test_save_appends_at_cursor_end_not_start():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*" more")
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert app.result == "existing text more"


async def test_escape_discards_changes():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*"more")
        await pilot.press("escape")
        await pilot.pause()

    assert app.result is None


async def test_status_reflects_live_word_count_and_goal_state():
    app = JournEditorApp("", writing_goal=2)
    async with app.run_test() as pilot:
        status = app.query_one("#status")
        assert "goal-met" not in status.classes

        await pilot.press(*"hi there")
        await pilot.pause()
        assert "goal-met" in status.classes
