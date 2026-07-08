"""Pure, metadata-only analytics over journal entries -- no crypto involved, since these
all operate on word_count/words_per_minute/dates rather than entry content. Mirrors the
existing streak.py/words.py pattern: logic here is decoupled from I/O so it's easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from journ.models import JournalEntry, Profile

SPARKLINE_LEVELS = "▁▂▃▄▅▆▇█"

WORD_MILESTONES = [1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 250_000, 500_000, 1_000_000]
ENTRY_MILESTONES = [10, 25, 50, 100, 250, 500, 1000]
STREAK_MILESTONES = [7, 14, 30, 60, 100, 365]

_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_TIME_BANDS = [
    ("Night", 0, 5),
    ("Morning", 5, 12),
    ("Afternoon", 12, 17),
    ("Evening", 17, 24),
]


@dataclass
class CalendarDay:
    day: date
    word_count: int | None
    wrote: bool


@dataclass
class TrendPoint:
    day: date
    word_count: int
    words_per_minute: float | None
    goal_met: bool


@dataclass
class Records:
    longest_entry_date: date | None
    longest_entry_words: int
    best_wpm_date: date | None
    best_wpm_value: float
    current_streak: int
    longest_streak: int


@dataclass
class PatternSummary:
    by_day_of_week: dict[str, int]
    by_time_of_day: dict[str, int]


def _entries_by_date(entries: list[JournalEntry]) -> dict[date, JournalEntry]:
    return {entry.entry_date: entry for entry in entries}


def build_calendar(
    entries: list[JournalEntry], weeks: int = 12, today: date | None = None
) -> list[list[CalendarDay]]:
    """Weeks of Mon-Sun CalendarDay rows, most recent week last, ending on `today`."""
    today = today or date.today()
    by_date = _entries_by_date(entries)
    end_of_week = today + timedelta(days=(6 - today.weekday()))
    start = end_of_week - timedelta(days=weeks * 7 - 1)

    grid: list[list[CalendarDay]] = []
    for week_index in range(weeks):
        week: list[CalendarDay] = []
        for day_index in range(7):
            day = start + timedelta(days=week_index * 7 + day_index)
            entry = by_date.get(day)
            word_count = entry.word_count if entry else None
            week.append(CalendarDay(day=day, word_count=word_count, wrote=entry is not None))
        grid.append(week)
    return grid


def consistency_score(
    entries: list[JournalEntry], window_days: int = 30, today: date | None = None
) -> float:
    """Fraction (0-1) of the last `window_days` days (inclusive of today) with an entry."""
    today = today or date.today()
    window_start = today - timedelta(days=window_days - 1)
    written_dates = {
        entry.entry_date for entry in entries if window_start <= entry.entry_date <= today
    }
    return len(written_dates) / window_days


def trend_series(
    entries: list[JournalEntry], days: int = 30, today: date | None = None
) -> list[TrendPoint]:
    """One TrendPoint per day for the last `days` days (oldest first), zero-filled gaps."""
    today = today or date.today()
    by_date = _entries_by_date(entries)
    start = today - timedelta(days=days - 1)

    points = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        entry = by_date.get(day)
        points.append(
            TrendPoint(
                day=day,
                word_count=(entry.word_count or 0) if entry else 0,
                words_per_minute=entry.words_per_minute if entry else None,
                goal_met=entry.accomplished_goal if entry else False,
            )
        )
    return points


def sparkline(values: list[float]) -> str:
    if not values:
        return ""
    max_value = max(values)
    if max_value <= 0:
        return SPARKLINE_LEVELS[0] * len(values)
    scale = len(SPARKLINE_LEVELS) - 1
    return "".join(
        SPARKLINE_LEVELS[min(scale, int((value / max_value) * scale))] for value in values
    )


def personal_records(entries: list[JournalEntry], profile: Profile) -> Records | None:
    entries_with_words = [e for e in entries if e.word_count is not None]
    if not entries_with_words:
        return None

    longest = max(entries_with_words, key=lambda e: e.word_count)
    wpm_entries = [e for e in entries_with_words if e.words_per_minute]
    best_wpm_entry = max(wpm_entries, key=lambda e: e.words_per_minute) if wpm_entries else None

    return Records(
        longest_entry_date=longest.entry_date,
        longest_entry_words=longest.word_count,
        best_wpm_date=best_wpm_entry.entry_date if best_wpm_entry else None,
        best_wpm_value=best_wpm_entry.words_per_minute if best_wpm_entry else 0.0,
        current_streak=profile.streak,
        longest_streak=profile.longest_streak,
    )


def writing_pattern(entries: list[JournalEntry]) -> PatternSummary:
    by_day = {name: 0 for name in _DAY_NAMES}
    by_time = {name: 0 for name, _, _ in _TIME_BANDS}

    for entry in entries:
        if not entry.started_at:
            continue
        started = datetime.fromisoformat(entry.started_at)
        by_day[_DAY_NAMES[started.weekday()]] += 1
        for name, start_hour, end_hour in _TIME_BANDS:
            if start_hour <= started.hour < end_hour:
                by_time[name] += 1
                break

    return PatternSummary(by_day_of_week=by_day, by_time_of_day=by_time)


def _thresholds_crossed(before: int, after: int, thresholds: list[int]) -> list[int]:
    return [t for t in thresholds if before < t <= after]


def detect_milestones(
    words_before: int,
    words_after: int,
    entries_before: int,
    entries_after: int,
    streak_before: int,
    streak_after: int,
) -> list[tuple[str, int]]:
    """Returns (kind, threshold) pairs for milestones newly crossed by this write."""
    words_crossed = _thresholds_crossed(words_before, words_after, WORD_MILESTONES)
    entries_crossed = _thresholds_crossed(entries_before, entries_after, ENTRY_MILESTONES)
    streak_crossed = _thresholds_crossed(streak_before, streak_after, STREAK_MILESTONES)

    milestones: list[tuple[str, int]] = []
    milestones += [("words", t) for t in words_crossed]
    milestones += [("entries", t) for t in entries_crossed]
    milestones += [("streak", t) for t in streak_crossed]
    return milestones


def suggest_goal(
    entries: list[JournalEntry], current_goal: int, days: int = 30, today: date | None = None
) -> int | None:
    """Suggests a rounder daily goal based on recent average word count, or None if the
    current goal is already close (within ~10%) to what's realistic."""
    today = today or date.today()
    window_start = today - timedelta(days=days - 1)
    recent = [
        e.word_count
        for e in entries
        if e.word_count is not None and window_start <= e.entry_date <= today
    ]
    if not recent:
        return None

    average = sum(recent) / len(recent)
    suggested = max(50, round(average / 50) * 50)
    if current_goal == 0 or abs(suggested - current_goal) / current_goal < 0.10:
        return None
    return suggested
