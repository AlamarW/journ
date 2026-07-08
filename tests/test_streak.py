from datetime import date, timedelta

from journ.streak import update_streak

DAY1 = date(2026, 7, 1)
DAY2 = DAY1 + timedelta(days=1)
DAY3 = DAY1 + timedelta(days=2)


def test_first_entry_starts_streak_at_one():
    streak, last_date = update_streak(0, None, DAY1, goal_met=True)
    assert (streak, last_date) == (1, DAY1)


def test_consecutive_day_increments():
    streak, last_date = update_streak(1, DAY1, DAY2, goal_met=True)
    assert (streak, last_date) == (2, DAY2)


def test_gap_day_resets_to_one():
    streak, last_date = update_streak(5, DAY1, DAY3, goal_met=True)
    assert (streak, last_date) == (1, DAY3)


def test_same_day_reentry_is_idempotent():
    # Regression test: re-saving today's entry twice must not double-increment
    # (this was the "streak incremented multiple times a day" bug).
    streak, last_date = update_streak(3, DAY2, DAY2, goal_met=True)
    assert (streak, last_date) == (3, DAY2)


def test_goal_not_met_does_not_change_streak():
    streak, last_date = update_streak(3, DAY1, DAY2, goal_met=False)
    assert (streak, last_date) == (3, DAY1)
