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

_WORD_RE = re.compile(r"[a-zA-Z']+")

# Small built-in stopword list -- deliberately not a dependency like nltk, which would be
# heavy relative to journ's footprint for what's just a common-words filter.
STOPWORDS = frozenset(
    """
    a about above after again against all am an and any are aren't as at be because been
    before being below between both but by can't cannot could couldn't did didn't do does
    doesn't doing don't down during each few for from further had hadn't has hasn't have
    haven't having he he'd he'll he's her here here's hers herself him himself his how
    how's i i'd i'll i'm i've if in into is isn't it it's its itself just let's me more
    most mustn't my myself no nor not of off on once only or other ought our ours
    ourselves out over own same shan't she she'd she'll she's should shouldn't so some
    such than that that's the their theirs them themselves then there there's these they
    they'd they'll they're they've this those through to too under until up very was
    wasn't we we'd we'll we're we've were weren't what what's when when's where where's
    which while who who's whom why why's with won't would wouldn't you you'd you'll
    you're you've your yours yourself yourselves
    """.split()
)


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
