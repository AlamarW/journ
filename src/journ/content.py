"""Pure functions over already-decrypted entry text. Crypto/DB access stays orchestrated in
actions.py (matching the existing _decode_entry pattern) so these are trivial to unit test
without mocking crypto.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from stop_words import get_stop_words

_WORD_RE = re.compile(r"[a-zA-Z']+")

# `stop-words` is a small, dependency-free package (unlike nltk, which needs a separate
# corpus download) -- its English list is far more thorough than a hand-rolled one, covering
# conversational filler (really, like, actually, just, very, ...) as well as the usual
# grammatical stopwords.
STOPWORDS = frozenset(get_stop_words("en"))


@dataclass
class DecryptedEntry:
    entry_date: date
    text: str
    word_count: int
    words_per_minute: float | None
    accomplished_goal: bool


def word_frequency(texts: list[str], top_n: int = 20) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for text in texts:
        for match in _WORD_RE.finditer(text.lower()):
            word = match.group()
            if len(word) >= 3 and word not in STOPWORDS:
                counts[word] += 1
    return counts.most_common(top_n)


def search_matches(
    entries: list[DecryptedEntry], query: str, context: int = 40
) -> list[tuple[date, str]]:
    """Case-insensitive substring search; one snippet per matching entry."""
    if not query:
        return []
    query_lower = query.lower()
    results = []
    for entry in entries:
        index = entry.text.lower().find(query_lower)
        if index == -1:
            continue
        start = max(0, index - context)
        end = min(len(entry.text), index + len(query) + context)
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(entry.text) else ""
        snippet = prefix + entry.text[start:end].replace("\n", " ") + suffix
        results.append((entry.entry_date, snippet))
    return results


def format_markdown(entries: list[DecryptedEntry]) -> str:
    sections = []
    for entry in sorted(entries, key=lambda e: e.entry_date):
        sections.append(f"## {entry.entry_date.isoformat()}\n\n{entry.text}\n")
    return "\n".join(sections)


def format_json(entries: list[DecryptedEntry]) -> str:
    payload = [
        {
            "date": entry.entry_date.isoformat(),
            "text": entry.text,
            "word_count": entry.word_count,
            "words_per_minute": entry.words_per_minute,
            "accomplished_goal": entry.accomplished_goal,
        }
        for entry in sorted(entries, key=lambda e: e.entry_date)
    ]
    return json.dumps(payload, indent=2)
