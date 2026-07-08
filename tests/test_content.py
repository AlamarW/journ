import json
from datetime import date

from journ import content
from journ.content import DecryptedEntry


def make_entry(day, text, word_count=None, wpm=42.0, goal_met=True):
    return DecryptedEntry(
        entry_date=day,
        text=text,
        word_count=word_count if word_count is not None else len(text.split()),
        words_per_minute=wpm,
        accomplished_goal=goal_met,
    )


def test_word_frequency_filters_stopwords_and_short_words():
    texts = ["The quick brown fox jumps over the lazy dog and the fox runs"]
    freq = dict(content.word_frequency(texts))

    assert "the" not in freq
    assert "and" not in freq
    assert "fox" in freq
    assert freq["fox"] == 2


def test_word_frequency_respects_top_n():
    texts = ["apple banana cherry date everyone forest garden"]
    top = content.word_frequency(texts, top_n=2)
    assert len(top) == 2


def test_search_matches_case_insensitive_with_snippet():
    entries = [
        make_entry(date(2026, 1, 1), "I went for a long walk in the rain today and loved it"),
        make_entry(date(2026, 1, 2), "Nothing much happened"),
    ]
    results = content.search_matches(entries, "WALK", context=5)

    assert len(results) == 1
    matched_date, snippet = results[0]
    assert matched_date == date(2026, 1, 1)
    assert "walk" in snippet.lower()


def test_search_matches_empty_query_returns_nothing():
    entries = [make_entry(date(2026, 1, 1), "some text")]
    assert content.search_matches(entries, "") == []


def test_format_markdown_sorted_by_date_with_headings():
    entries = [
        make_entry(date(2026, 1, 2), "second entry"),
        make_entry(date(2026, 1, 1), "first entry"),
    ]
    md = content.format_markdown(entries)

    assert md.index("## 2026-01-01") < md.index("## 2026-01-02")
    assert "first entry" in md
    assert "second entry" in md


def test_format_json_round_trips_fields():
    entries = [make_entry(date(2026, 1, 1), "hello world", word_count=2, wpm=10.0)]
    payload = json.loads(content.format_json(entries))

    assert payload[0]["date"] == "2026-01-01"
    assert payload[0]["text"] == "hello world"
    assert payload[0]["word_count"] == 2
    assert payload[0]["words_per_minute"] == 10.0
    assert payload[0]["accomplished_goal"] is True
