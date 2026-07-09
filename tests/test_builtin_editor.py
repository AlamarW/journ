from datetime import date

from journ import builtin_editor
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


def test_drain_pending_console_input_flushes_console_input_buffer(monkeypatch):
    calls = []

    class _FakeKernel32:
        def GetStdHandle(self, handle_id):
            calls.append(("GetStdHandle", handle_id))
            return 42

        def FlushConsoleInputBuffer(self, handle):
            calls.append(("FlushConsoleInputBuffer", handle))

    class _FakeWindll:
        kernel32 = _FakeKernel32()

    monkeypatch.setattr(builtin_editor.ctypes, "windll", _FakeWindll(), raising=False)
    monkeypatch.setattr(builtin_editor.os, "name", "nt")

    builtin_editor._drain_pending_console_input()

    assert ("GetStdHandle", builtin_editor._STD_INPUT_HANDLE) in calls
    assert ("FlushConsoleInputBuffer", 42) in calls


def test_drain_pending_console_input_is_a_noop_off_windows(monkeypatch):
    class _FakeKernel32:
        def GetStdHandle(self, handle_id):
            raise AssertionError("GetStdHandle should not be called off Windows")

        def FlushConsoleInputBuffer(self, handle):
            raise AssertionError("FlushConsoleInputBuffer should not be called off Windows")

    class _FakeWindll:
        kernel32 = _FakeKernel32()

    monkeypatch.setattr(builtin_editor.ctypes, "windll", _FakeWindll(), raising=False)
    monkeypatch.setattr(builtin_editor.os, "name", "posix")

    builtin_editor._drain_pending_console_input()
