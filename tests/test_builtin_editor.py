"""journ's editor is quire's plus a footer and the private toggle.

The discard guard, the save keys, and the never-lose-text guarantee are quire's and are
tested there against every host. What is tested here is what journ actually contributes --
the goal-aware footer and the private lifecycle -- plus one end-to-end check that the guard
is really wired, since an adapter mistake would not show up in quire's own suite.
"""

from datetime import date

from journ.builtin_editor import build_journ_editor, status_text


class TestStatusText:
    def test_shows_progress_against_the_goal(self):
        assert status_text(5, 100, private=False, entry_date=None) == (
            "5 / 100 words | in progress"
        )

    def test_reports_the_goal_as_met(self):
        assert status_text(100, 100, private=False, entry_date=None) == (
            "100 / 100 words | goal met"
        )

    def test_includes_the_private_indicator_only_when_private(self):
        assert "PRIVATE" not in status_text(5, 100, private=False, entry_date=None)
        assert "PRIVATE" in status_text(5, 100, private=True, entry_date=None)

    def test_includes_the_entry_date_only_when_set(self):
        """A past day is labelled so it is never mistaken for today's entry."""
        assert "Editing" not in status_text(5, 100, private=False, entry_date=None)
        assert "Editing 2026-07-01" in status_text(
            5, 100, private=False, entry_date=date(2026, 7, 1)
        )


class TestEditorIntegration:
    async def test_footer_tracks_live_word_count_and_goal_state(self):
        app, _ = build_journ_editor("", writing_goal=2)
        async with app.run_test() as pilot:
            status = app.query_one("#status")
            assert "emphasis" not in status.classes

            await pilot.press(*"hi there")
            await pilot.pause()
            assert "0 / 2" not in str(status.render())
            assert "goal met" in str(status.render())
            assert "emphasis" in status.classes

    async def test_ctrl_p_toggles_private(self):
        app, flag = build_journ_editor("existing text", writing_goal=100)
        async with app.run_test() as pilot:
            assert flag.private is False

            await pilot.press("ctrl+p")
            await pilot.pause()
            assert flag.private is True
            assert "PRIVATE" in str(app.query_one("#status").render())

            await pilot.press("ctrl+p")
            await pilot.pause()
            assert flag.private is False

    async def test_initial_private_carries_through_to_save(self):
        app, flag = build_journ_editor("existing text", writing_goal=100, initial_private=True)
        async with app.run_test() as pilot:
            assert "PRIVATE" in str(app.query_one("#status").render())
            await pilot.press("ctrl+w")
            await pilot.pause()

        assert app.result.saved is True
        assert flag.private is True

    async def test_saving_reflects_the_private_state_at_save_time(self):
        app, flag = build_journ_editor("existing text", writing_goal=100)
        async with app.run_test() as pilot:
            await pilot.press("ctrl+p")
            await pilot.press("ctrl+w")
            await pilot.pause()

        assert app.result.saved is True
        assert flag.private is True

    async def test_typing_appends_at_the_cursor_end(self):
        app, _ = build_journ_editor("existing text", writing_goal=100)
        async with app.run_test() as pilot:
            await pilot.press(*" more")
            await pilot.press("ctrl+w")
            await pilot.pause()

        assert app.result.text == "existing text more"

    async def test_discard_guard_is_wired_through_journs_editor(self):
        """quire owns the guard, but a broken adapter could still bypass it here."""
        app, _ = build_journ_editor("existing text", writing_goal=100)
        async with app.run_test() as pilot:
            await pilot.press(*" more")
            await pilot.press("escape")
            await pilot.pause()
            assert app.result is None, "first press must not discard"

            await pilot.press("escape")
            await pilot.pause()

        assert app.result.saved is False
        assert app.result.text == "existing text more", "discarded text still comes back"
