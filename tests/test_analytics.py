from datetime import date, timedelta

from journ import analytics
from journ.models import JournalEntry, Profile

TODAY = date(2026, 7, 8)  # a Wednesday


def make_entry(day, word_count=100, wpm=50.0, goal_met=True, started_at=None):
    return JournalEntry(
        entry_date=day,
        content=b"irrelevant",
        is_encrypted=False,
        words_per_minute=wpm,
        accomplished_goal=goal_met,
        updated_at=day.isoformat(),
        word_count=word_count,
        started_at=started_at,
    )


def make_profile(streak=0, longest_streak=0, writing_goal=750):
    return Profile(
        writing_goal=writing_goal,
        streak=streak,
        streak_last_entry_date=None,
        kdf_salt=None,
        passphrase_canary=None,
        longest_streak=longest_streak,
    )


def test_build_calendar_marks_written_and_unwritten_days():
    entries = [make_entry(TODAY, word_count=321)]
    grid = analytics.build_calendar(entries, weeks=2, today=TODAY)

    assert len(grid) == 2
    assert all(len(week) == 7 for week in grid)

    flat = [day for week in grid for day in week]
    today_cell = next(d for d in flat if d.day == TODAY)
    assert today_cell.wrote is True
    assert today_cell.word_count == 321

    yesterday_cell = next(d for d in flat if d.day == TODAY - timedelta(days=1))
    assert yesterday_cell.wrote is False
    assert yesterday_cell.word_count is None


def test_consistency_score_counts_only_window_days():
    entries = [
        make_entry(TODAY),
        make_entry(TODAY - timedelta(days=1)),
        make_entry(TODAY - timedelta(days=40)),  # outside a 30-day window
    ]
    score = analytics.consistency_score(entries, window_days=30, today=TODAY)
    assert score == 2 / 30


def test_trend_series_fills_gaps_with_zero():
    entries = [make_entry(TODAY, word_count=200)]
    points = analytics.trend_series(entries, days=3, today=TODAY)

    assert [p.day for p in points] == [TODAY - timedelta(days=2), TODAY - timedelta(days=1), TODAY]
    assert points[-1].word_count == 200
    assert points[0].word_count == 0
    assert points[0].goal_met is False


def test_sparkline_edge_cases():
    assert analytics.sparkline([]) == ""
    assert analytics.sparkline([0, 0, 0]) == analytics.SPARKLINE_LEVELS[0] * 3
    assert analytics.sparkline([10])[-1] == analytics.SPARKLINE_LEVELS[-1]


def test_personal_records_none_when_no_word_counts():
    assert analytics.personal_records([], make_profile()) is None
    unbackfilled = [make_entry(TODAY, word_count=None)]
    assert analytics.personal_records(unbackfilled, make_profile()) is None


def test_personal_records_picks_max_words_and_wpm():
    entries = [
        make_entry(TODAY - timedelta(days=1), word_count=100, wpm=30.0),
        make_entry(TODAY, word_count=500, wpm=80.0),
    ]
    profile = make_profile(streak=3, longest_streak=10)
    records = analytics.personal_records(entries, profile)

    assert records.longest_entry_date == TODAY
    assert records.longest_entry_words == 500
    assert records.best_wpm_date == TODAY
    assert records.best_wpm_value == 80.0
    assert records.current_streak == 3
    assert records.longest_streak == 10


def test_writing_pattern_buckets_by_day_and_time():
    morning = f"{TODAY.isoformat()}T08:00:00"
    evening = f"{(TODAY - timedelta(days=1)).isoformat()}T19:30:00"
    entries = [
        make_entry(TODAY, started_at=morning),
        make_entry(TODAY - timedelta(days=1), started_at=evening),
        make_entry(TODAY - timedelta(days=2), started_at=None),  # unbackfilled, skipped
    ]
    pattern = analytics.writing_pattern(entries)

    assert pattern.by_time_of_day["Morning"] == 1
    assert pattern.by_time_of_day["Evening"] == 1
    assert sum(pattern.by_day_of_week.values()) == 2


def test_detect_milestones_crossing_and_not_crossing():
    crossed = analytics.detect_milestones(
        words_before=900,
        words_after=1200,
        entries_before=9,
        entries_after=10,
        streak_before=6,
        streak_after=7,
    )
    assert ("words", 1_000) in crossed
    assert ("entries", 10) in crossed
    assert ("streak", 7) in crossed

    not_crossed = analytics.detect_milestones(
        words_before=1_500,
        words_after=1_800,
        entries_before=12,
        entries_after=13,
        streak_before=8,
        streak_after=9,
    )
    assert not_crossed == []


def test_detect_milestones_can_cross_multiple_thresholds_at_once():
    crossed = analytics.detect_milestones(
        words_before=900,
        words_after=6_000,
        entries_before=0,
        entries_after=0,
        streak_before=0,
        streak_after=0,
    )
    kinds = [t for kind, t in crossed if kind == "words"]
    assert kinds == [1_000, 5_000]


def test_suggest_goal_no_data_returns_none():
    assert analytics.suggest_goal([], current_goal=750, today=TODAY) is None


def test_suggest_goal_close_to_current_returns_none():
    entries = [make_entry(TODAY, word_count=760)]
    assert analytics.suggest_goal(entries, current_goal=750, today=TODAY) is None


def test_suggest_goal_meaningfully_different_suggests_rounded_value():
    entries = [make_entry(TODAY - timedelta(days=i), word_count=400) for i in range(5)]
    suggested = analytics.suggest_goal(entries, current_goal=750, today=TODAY)
    assert suggested == 400


def test_suggest_goal_with_zero_current_goal_still_suggests():
    entries = [make_entry(TODAY - timedelta(days=i), word_count=400) for i in range(5)]
    suggested = analytics.suggest_goal(entries, current_goal=0, today=TODAY)
    assert suggested == 400
