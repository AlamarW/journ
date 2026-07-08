from journ.builtin_editor import JournEditorApp


async def test_save_appends_at_cursor_end_not_start():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press(*" more")
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert app.result.text == "existing text more"
    assert app.result.private is False


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


async def test_save_reflects_private_state_at_save_time():
    app = JournEditorApp("existing text", writing_goal=100)
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        await pilot.press("ctrl+s")
        await pilot.pause()

    assert app.result.private is True


async def test_initial_private_true_carries_through_to_save():
    app = JournEditorApp("existing text", writing_goal=100, initial_private=True)
    async with app.run_test() as pilot:
        assert app.is_private is True
        assert "PRIVATE" in app._status_text(2)

        await pilot.press("ctrl+s")
        await pilot.pause()

    assert app.result.private is True
