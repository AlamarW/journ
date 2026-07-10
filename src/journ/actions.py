"""Shared verbs used by both the one-shot CLI commands (cli.py) and the REPL (shell.py),
so each behavior has exactly one implementation.
"""

from __future__ import annotations

import calendar
import getpass
import os
import subprocess
from dataclasses import dataclass, replace
from datetime import date, datetime
from pathlib import Path

from journ import analytics, config, content, crypto, mcp_keychain, ui
from journ.builtin_editor import run_builtin_editor
from journ.content import DecryptedEntry
from journ.db import Database
from journ.models import JournalEntry, Profile
from journ.streak import recompute_streak, update_streak
from journ.words import count_words, format_elapsed, words_per_minute


class PassphraseError(Exception):
    """Raised when a passphrase is required but can't be obtained/verified."""


def ensure_profile(db: Database) -> tuple[Profile, bytes | None]:
    """Return the local profile, running first-time setup if one doesn't exist yet.

    The second element is the freshly-derived encryption key if a passphrase was just set
    during this call, so callers don't have to immediately re-prompt for it; it's None
    whenever the profile already existed or no passphrase was set.
    """
    profile = db.get_profile()
    if profile is not None:
        return profile, None

    print("Welcome to journ! Let's set up your local profile.\n")
    while True:
        goal_input = input("Daily writing goal, in words (e.g. 750) -> ").strip()
        try:
            writing_goal = int(goal_input)
            break
        except ValueError:
            print("Please enter a whole number.")

    kdf_salt = canary = key = None
    wants_passphrase = (
        input(
            "Set a passphrase to encrypt your entries? Recommended for personal journals. (y/N) -> "
        )
        .strip()
        .lower()
    )
    if wants_passphrase == "y":
        kdf_salt, canary, key = _prompt_new_passphrase()

    profile = db.create_profile(writing_goal, kdf_salt, canary)
    print("Profile created.\n")
    return profile, key


def _prompt_new_passphrase() -> tuple[bytes, bytes, bytes]:
    while True:
        passphrase = getpass.getpass("New passphrase -> ")
        confirm = getpass.getpass("Confirm passphrase -> ")
        if not passphrase:
            print("Passphrase can't be empty.")
            continue
        if passphrase != confirm:
            print("Passphrases didn't match, try again.")
            continue
        salt, canary = crypto.setup_passphrase(passphrase)
        key = crypto.derive_key(passphrase, salt)
        return salt, canary, key


def unlock(profile: Profile, attempts: int = 3) -> bytes | None:
    """Prompt for the passphrase if one is set; returns the derived key, or None if no
    passphrase is set (entries are stored as plaintext in that case)."""
    if not profile.has_passphrase:
        return None
    for _ in range(attempts):
        passphrase = getpass.getpass("Passphrase: ")
        key = crypto.verify_passphrase(passphrase, profile.kdf_salt, profile.passphrase_canary)
        if key is not None:
            return key
        print("Incorrect passphrase, try again.")
    raise PassphraseError("Too many incorrect passphrase attempts.")


def _decode_entry(db: Database, entry: JournalEntry, key: bytes | None) -> str:
    if entry.is_encrypted:
        if key is None:
            raise PassphraseError("This entry is encrypted but no passphrase was provided.")
        text = crypto.decrypt_text(key, entry.content)
    else:
        text = entry.content.decode("utf-8")

    if entry.word_count is None:
        # Lazily backfill entries written before word_count was tracked (see db._migrate).
        entry.word_count = count_words(text)
        db.update_word_count(entry.entry_date, entry.word_count)

    return text


def _encode_entry(text: str, key: bytes | None) -> tuple[bytes, bool]:
    if key is not None:
        return crypto.encrypt_text(key, text), True
    return text.encode("utf-8"), False


def all_decrypted(
    db: Database, profile: Profile, key: bytes | None, entries: list[JournalEntry] | None = None
) -> list[DecryptedEntry]:
    """Decrypts entries into DecryptedEntry text. Defaults to every entry in the journal, but
    accepts a pre-filtered subset (see filter_private) so callers can exclude entries from
    decryption entirely rather than decrypting everything and filtering the result."""
    if entries is None:
        entries = db.all_entries()
    if not entries:
        return []
    if key is None:
        key = unlock(profile)
    return [
        DecryptedEntry(
            entry_date=entry.entry_date,
            text=(text := _decode_entry(db, entry, key)),
            word_count=entry.word_count if entry.word_count is not None else count_words(text),
            words_per_minute=entry.words_per_minute,
            accomplished_goal=entry.accomplished_goal,
        )
        for entry in entries
    ]


def filter_private(entries: list[JournalEntry], include_private: bool) -> list[JournalEntry]:
    """Excludes private entries unless include_private=True. Pure and DB/crypto-free so
    Tier-3 gating can be tested without touching the database."""
    if include_private:
        return entries
    return [e for e in entries if not e.private]


def _update_streak_and_longest(
    db: Database, profile: Profile, new_streak: int, new_last_entry_date: date | None
) -> None:
    db.update_streak(new_streak, new_last_entry_date)
    if new_streak > profile.longest_streak:
        db.update_longest_streak(new_streak)


def reconcile_streak(db: Database) -> int:
    """Recomputes and persists streak/longest_streak from every entry's accomplished_goal flag,
    rather than update_streak's incremental day-over-day model. Call this after any write that
    can target a past date, since a backdated entry filling a gap can't be reasoned about one
    day at a time. Returns the new streak (0 if no profile exists yet)."""
    profile = db.get_profile()
    if profile is None:
        return 0
    qualifying_dates = [e.entry_date for e in db.all_entries() if e.accomplished_goal]
    streak, longest, last_entry_date = recompute_streak(qualifying_dates)
    db.update_streak(streak, last_entry_date)
    db.update_longest_streak(longest)
    return streak


def write_today_entry(db: Database, private: bool | None = None) -> None:
    """private=None preserves today's existing entry's current private flag if editing one
    (False for a new entry) -- an explicit bool always overrides. For the built-in editor this
    is only the *initial* toggle state, since ctrl+p can change it during the session; for an
    external $EDITOR there's no interactive UI to toggle it mid-session, so this is the only
    control."""
    profile, key = ensure_profile(db)
    if key is None:
        key = unlock(profile)

    today = date.today()
    existing = db.get_entry(today)
    existing_text = _decode_entry(db, existing, key) if existing else ""
    previous_word_count = count_words(existing_text)
    initial_started_at = existing.started_at if existing and existing.started_at else None
    initial_private = existing.private if existing else False
    if private is not None:
        initial_private = private

    editor = config.get_editor()
    used_builtin = editor == config.BUILTIN_EDITOR

    start_time = datetime.now()
    if used_builtin:
        # Held in memory only -- unlike the external-editor path below, this never writes
        # plaintext to disk.
        result = run_builtin_editor(existing_text, profile.writing_goal, initial_private)
        if result is None:
            print("Discarded -- no changes saved.")
            return
        text = result.text
        is_private = result.private
    else:
        is_private = initial_private
        config.journ_tmp_dir.mkdir(parents=True, exist_ok=True)
        scratch_path = config.journ_tmp_dir / f"{today.isoformat()}.txt"

        for leftover in config.journ_tmp_dir.glob("*.txt"):
            if leftover != scratch_path:
                leftover.unlink()

        scratch_path.write_text(existing_text, encoding="utf-8")
        try:
            subprocess.run(
                config.editor_argv(editor) + [str(scratch_path)],
                shell=(os.name == "nt"),
            )
        except FileNotFoundError:
            scratch_path.unlink(missing_ok=True)
            print(
                f"Could not launch editor '{editor}'. Set EDITOR to a valid command and try again."
            )
            return
        text = scratch_path.read_text(encoding="utf-8")
        scratch_path.unlink(missing_ok=True)
    elapsed = datetime.now() - start_time

    word_count = count_words(text)
    goal_met = word_count >= profile.writing_goal
    new_words_this_session = max(0, word_count - previous_word_count)
    wpm = words_per_minute(new_words_this_session, elapsed)

    # The editor session above can run for an arbitrarily long time, so only the final
    # read-totals -> write -> streak-update sequence is wrapped atomically -- holding the
    # write lock for the whole editing session would block any other writer (e.g. an MCP
    # save_conversation_entry call) for as long as the user is typing.
    with db.locked_for_write():
        words_before, entries_before = db.aggregate_totals()

        content_bytes, is_encrypted = _encode_entry(text, key)
        db.upsert_entry(
            JournalEntry(
                entry_date=today,
                content=content_bytes,
                is_encrypted=is_encrypted,
                words_per_minute=wpm,
                accomplished_goal=goal_met,
                updated_at=datetime.now().isoformat(),
                word_count=word_count,
                started_at=initial_started_at or start_time.isoformat(),
                private=is_private,
            )
        )

        words_after, entries_after = db.aggregate_totals()

        new_streak, new_last_entry_date = update_streak(
            profile.streak, profile.streak_last_entry_date, today, goal_met
        )
        _update_streak_and_longest(db, profile, new_streak, new_last_entry_date)

        milestones = analytics.detect_milestones(
            words_before=words_before,
            words_after=words_after,
            entries_before=entries_before,
            entries_after=entries_after,
            streak_before=profile.streak,
            streak_after=new_streak,
        )

    ui.print_write_summary(
        word_count=word_count,
        writing_goal=profile.writing_goal,
        goal_met=goal_met,
        elapsed=elapsed,
        words_per_minute=wpm,
        streak=new_streak,
        streak_changed=(new_streak != profile.streak),
        milestones=milestones,
        private=is_private,
    )


def edit_entry(db: Database, entry_date: date, private: bool | None = None) -> None:
    """Retroactively edit a past entry, or backfill a day that has no entry at all. Unlike
    write_today_entry there's no live session to time, so words_per_minute and started_at are
    always carried over from the existing entry untouched (None for a brand-new backfilled
    entry) rather than recomputed -- fabricating either would misrepresent a session that
    never happened.

    Streak/longest-streak are always fully reconciled afterward (streak.recompute_streak via
    reconcile_streak), never incrementally patched: a retroactive edit can newly satisfy a
    day's goal it previously missed (extending or starting a streak run wherever the date
    falls) or newly fall short of a goal it previously met (breaking a run). Both directions
    are intentional -- the streak should always honestly reflect accomplished_goal across every
    entry, not just the ones edited most recently.
    """
    if entry_date >= date.today():
        print("Use `write` to edit today's entry.")
        return

    profile, key = ensure_profile(db)
    if key is None:
        key = unlock(profile)

    existing = db.get_entry(entry_date)
    is_new_entry = existing is None
    existing_text = _decode_entry(db, existing, key) if existing else ""
    initial_private = existing.private if existing else False
    if private is not None:
        initial_private = private

    editor = config.get_editor()
    used_builtin = editor == config.BUILTIN_EDITOR

    if used_builtin:
        result = run_builtin_editor(
            existing_text, profile.writing_goal, initial_private, entry_date=entry_date
        )
        if result is None:
            print("Discarded -- no changes saved.")
            return
        text = result.text
        is_private = result.private
    else:
        is_private = initial_private
        config.journ_tmp_dir.mkdir(parents=True, exist_ok=True)
        scratch_path = config.journ_tmp_dir / f"{entry_date.isoformat()}.txt"

        for leftover in config.journ_tmp_dir.glob("*.txt"):
            if leftover != scratch_path:
                leftover.unlink()

        scratch_path.write_text(existing_text, encoding="utf-8")
        print(f"Editing entry for {entry_date.isoformat()} in {editor}...")
        try:
            subprocess.run(
                config.editor_argv(editor) + [str(scratch_path)],
                shell=(os.name == "nt"),
            )
        except FileNotFoundError:
            scratch_path.unlink(missing_ok=True)
            print(
                f"Could not launch editor '{editor}'. Set EDITOR to a valid command and try again."
            )
            return
        text = scratch_path.read_text(encoding="utf-8")
        scratch_path.unlink(missing_ok=True)

    word_count = count_words(text)
    goal_met = word_count >= profile.writing_goal

    with db.locked_for_write():
        words_before, entries_before = db.aggregate_totals()

        content_bytes, is_encrypted = _encode_entry(text, key)
        db.upsert_entry(
            JournalEntry(
                entry_date=entry_date,
                content=content_bytes,
                is_encrypted=is_encrypted,
                words_per_minute=existing.words_per_minute if existing else None,
                accomplished_goal=goal_met,
                updated_at=datetime.now().isoformat(),
                word_count=word_count,
                started_at=existing.started_at if existing else None,
                private=is_private,
            )
        )

        words_after, entries_after = db.aggregate_totals()
        streak_after = reconcile_streak(db)

        milestones = analytics.detect_milestones(
            words_before=words_before,
            words_after=words_after,
            entries_before=entries_before,
            entries_after=entries_after,
            streak_before=profile.streak,
            streak_after=streak_after,
        )

    ui.print_edit_summary(
        entry_date=entry_date,
        is_new_entry=is_new_entry,
        word_count=word_count,
        writing_goal=profile.writing_goal,
        goal_met=goal_met,
        streak=streak_after,
        streak_changed=(streak_after != profile.streak),
        milestones=milestones,
        private=is_private,
    )


@dataclass
class ConversationTurn:
    role: str  # "user" or "assistant"
    text: str


@dataclass
class ConversationSaveResult:
    entry_date: date
    word_count: int
    accomplished_goal: bool
    streak: int
    streak_changed: bool
    milestones: list[tuple[str, int]]


def _format_transcript(turns: list[ConversationTurn]) -> str:
    speaker = {"user": "You", "assistant": "Assistant"}
    return "\n\n".join(f"{speaker.get(t.role, t.role)}: {t.text}" for t in turns)


def save_conversation_entry(
    db: Database,
    entry_date: date,
    turns: list[ConversationTurn],
    key: bytes | None,
    private: bool | None = None,
) -> ConversationSaveResult:
    """Tier-2 MCP write action: appends a conversation transcript to entry_date's entry
    (creating it if absent). The stored content is the full transcript (both sides), but only
    the user's own turns count toward word_count/goal/streak -- the assistant's words never
    do. words_per_minute is never computed or overwritten here (no meaningful typing-speed
    signal in a back-and-forth conversation); if merging into an entry that already has a real
    value from an earlier editor session, it's preserved untouched.

    private=None preserves whatever the entry's current private flag is (False for a new
    entry) rather than defaulting to False -- an explicit bool always overrides.

    If this exact transcript is already the tail of the stored entry -- i.e. an MCP client
    retried the same tool call after e.g. a timeout -- the text isn't appended again and the
    words aren't double-counted. This is a pragmatic exact-suffix heuristic, not a real
    idempotency key, since there's no request-id tracking; a second call with a genuinely
    identical transcript would also be treated as a retry, but that's an acceptable trade-off
    for a journal.

    When entry_date is today, streak/longest-streak update incrementally via
    streak.update_streak, same as write_today_entry. A backdated entry_date instead
    reconciles the whole streak from scratch (streak.recompute_streak), since
    update_streak's day-over-day model can't reason about a gap being filled after the
    fact. Word/entry milestones (pure aggregate-total deltas) fire regardless of date.

    key must already be resolved by the caller -- this never calls unlock() itself, since an
    MCP tool call must never block on an interactive passphrase prompt.
    """
    with db.locked_for_write():
        profile = db.get_profile()
        if profile is None:
            raise ValueError(
                "No profile exists yet -- run `journ` once to finish first-time setup."
            )

        existing = db.get_entry(entry_date)
        existing_text = _decode_entry(db, existing, key) if existing else ""
        # _decode_entry backfills existing.word_count in place if it was None -- read it only
        # after that call, not before.
        existing_word_count = existing.word_count if existing else 0

        user_text = "\n\n".join(t.text for t in turns if t.role == "user")
        new_user_words = count_words(user_text)

        transcript_text = _format_transcript(turns)
        is_retry = bool(transcript_text) and existing_text.endswith(transcript_text)
        if is_retry:
            full_text = existing_text
            word_count = existing_word_count
        else:
            full_text = (
                f"{existing_text}\n\n{transcript_text}" if existing_text else transcript_text
            )
            word_count = existing_word_count + new_user_words

        goal_met = word_count >= profile.writing_goal
        wpm = existing.words_per_minute if existing else None

        if private is None:
            is_private = existing.private if existing else False
        else:
            is_private = private

        started_at = (
            existing.started_at if existing and existing.started_at else datetime.now().isoformat()
        )

        words_before, entries_before = db.aggregate_totals()
        content_bytes, is_encrypted = _encode_entry(full_text, key)
        db.upsert_entry(
            JournalEntry(
                entry_date=entry_date,
                content=content_bytes,
                is_encrypted=is_encrypted,
                words_per_minute=wpm,
                accomplished_goal=goal_met,
                updated_at=datetime.now().isoformat(),
                word_count=word_count,
                started_at=started_at,
                private=is_private,
            )
        )
        words_after, entries_after = db.aggregate_totals()

        if entry_date == date.today():
            streak_after, new_last_entry_date = update_streak(
                profile.streak, profile.streak_last_entry_date, entry_date, goal_met
            )
            _update_streak_and_longest(db, profile, streak_after, new_last_entry_date)
        else:
            # A backdated save can fill a gap or start/extend a streak that update_streak's
            # today-only incremental model can't react to -- recompute from scratch instead.
            streak_after = reconcile_streak(db)
        streak_changed = streak_after != profile.streak

        milestones = analytics.detect_milestones(
            words_before=words_before,
            words_after=words_after,
            entries_before=entries_before,
            entries_after=entries_after,
            streak_before=profile.streak,
            streak_after=streak_after,
        )

    return ConversationSaveResult(
        entry_date=entry_date,
        word_count=word_count,
        accomplished_goal=goal_met,
        streak=streak_after,
        streak_changed=streak_changed,
        milestones=milestones,
    )


def show_streak(db: Database) -> None:
    profile, _key = ensure_profile(db)
    ui.print_streak_line(profile.streak)


def show_last_entry(db: Database) -> None:
    profile, key = ensure_profile(db)
    entry = db.latest_entry()
    if entry is None:
        print("You haven't written anything yet.")
        return
    if entry.word_count is None:
        if key is None:
            key = unlock(profile)
        _decode_entry(db, entry, key)
    print(
        f"Your most recent entry ({entry.entry_date.isoformat()}) is {entry.word_count} "
        f"words; your goal is {profile.writing_goal} words."
    )


def show_stats(db: Database) -> None:
    profile, key = ensure_profile(db)
    entries = db.all_entries()
    if not entries:
        print("You haven't written anything yet.")
        return

    unbackfilled = [e for e in entries if e.word_count is None]
    if unbackfilled:
        if key is None:
            key = unlock(profile)
        for entry in unbackfilled:
            _decode_entry(db, entry, key)

    total_words, entry_count = db.aggregate_totals()
    avg_wpm = _average_wpm(entries)
    ui.print_stats_table(avg_wpm=avg_wpm, total_words=total_words, entry_count=entry_count)


def set_goal(db: Database, new_goal: int | None) -> None:
    profile, _key = ensure_profile(db)
    if new_goal is None:
        print(f"Your current daily writing goal is {profile.writing_goal} words.")
        return
    db.update_goal(new_goal)
    print(f"Daily writing goal updated to {new_goal} words.")


def manage_editor(reconfigure: bool) -> None:
    """Show or change the configured editor. Unlike the other actions this doesn't touch
    the database -- editor choice is machine-level config, not profile data."""
    if reconfigure:
        chosen = config.prompt_editor_choice()
        config.save_editor_choice(chosen)
        label = "journ's built-in editor" if chosen == config.BUILTIN_EDITOR else chosen
        print(f"Using {label} going forward.")
        return

    editor = os.getenv("EDITOR")
    if editor:
        print(f"Currently using: {editor} (from $EDITOR)")
        return

    saved = config.read_saved_editor()
    if saved:
        label = "journ's built-in editor" if saved == config.BUILTIN_EDITOR else saved
        print(f"Currently using: {label} (saved choice)")
        return

    if os.name == "nt":
        print("Not configured yet -- you'll be prompted to pick one the next time you write.")
    else:
        print("Currently using: nano (default -- no EDITOR set or saved choice)")
    print("Run `journ editor set` to choose (including journ's built-in editor).")


def manage_passphrase(db: Database, action: str) -> None:
    """action is one of: 'set', 'change', 'remove'."""
    profile, _key = ensure_profile(db)

    if action == "set":
        if profile.has_passphrase:
            print("A passphrase is already set; use 'change' instead.")
            return
        kdf_salt, canary, new_key = _prompt_new_passphrase()
        _reencrypt_all(db, None, kdf_salt, canary, new_key)
        print("Passphrase set. Your entries are now encrypted.")

    elif action == "change":
        if not profile.has_passphrase:
            print("No passphrase is set; use 'set' instead.")
            return
        old_key = unlock(profile)
        kdf_salt, canary, new_key = _prompt_new_passphrase()
        _reencrypt_all(db, old_key, kdf_salt, canary, new_key)
        print("Passphrase changed.")

    elif action == "remove":
        if not profile.has_passphrase:
            print("No passphrase is set.")
            return
        old_key = unlock(profile)
        _reencrypt_all(db, old_key, None, None, None)
        print("Passphrase removed. Your entries are now stored unencrypted.")

    else:
        raise ValueError(f"Unknown passphrase action: {action}")


def _reencrypt_all(
    db: Database,
    old_key: bytes | None,
    new_salt: bytes | None,
    new_canary: bytes | None,
    new_key: bytes | None,
) -> None:
    for entry in db.all_entries():
        text = _decode_entry(db, entry, old_key)
        content_bytes, is_encrypted = _encode_entry(text, new_key)
        db.upsert_entry(replace(entry, content=content_bytes, is_encrypted=is_encrypted))
    db.set_passphrase(new_salt, new_canary)


def mcp_unlock(db: Database) -> None:
    """Caches the derived passphrase key in the OS credential store, so a headlessly-spawned
    `journ mcp serve --content` can decrypt content without an interactive prompt."""
    profile, _key = ensure_profile(db)
    if not profile.has_passphrase:
        print(
            "This journal has no passphrase -- nothing to cache. `journ mcp serve --content` "
            "will work without unlocking."
        )
        return
    key = unlock(profile)
    try:
        mcp_keychain.cache_key(key)
    except mcp_keychain.KeychainError as exc:
        print(f"Could not cache the key: {exc}")
        return
    print("Key cached indefinitely in your OS credential store -- run `journ mcp lock` when done.")


def mcp_lock() -> None:
    mcp_keychain.clear_cached_key()
    print("Cached key removed.")


def mcp_status() -> None:
    cached_at = mcp_keychain.get_cached_at()
    if cached_at is None:
        print(
            "No key is currently cached. Run `journ mcp unlock` before using "
            "`journ mcp serve --content` on an encrypted journal."
        )
        return
    elapsed_str = format_elapsed(datetime.now() - cached_at)
    print(
        f"A key has been cached for {elapsed_str}. Run `journ mcp lock` when you're done "
        "using content-tier MCP tools."
    )


# --- metadata-only analytics (no passphrase needed once word_count/started_at are backfilled) ---
#
# Each of these is split into a get_* data function (pure over db.all_entries()/get_profile(),
# safe to call from an MCP tool with no key at all) and a thin show_*/action print wrapper used
# by the CLI/shell. The get_* functions deliberately call db.get_profile() directly rather than
# ensure_profile(db), since ensure_profile can trigger an interactive first-run input() prompt
# that must never be reachable from a non-interactive MCP tool call.


@dataclass
class StatsTotals:
    total_words: int
    entry_count: int
    avg_words_per_minute: float


def get_calendar_data(
    db: Database, weeks: int = 12, today: date | None = None
) -> tuple[list[list[analytics.CalendarDay]], float]:
    # Private only hides an entry's text, not the fact you wrote it -- this is metadata
    # (word count, whether you wrote that day), so private entries count same as any other.
    entries = db.all_entries()
    grid = analytics.build_calendar(entries, weeks=weeks, today=today)
    score = analytics.consistency_score(entries, today=today)
    return grid, score


def show_calendar(db: Database) -> None:
    ensure_profile(db)
    grid, score = get_calendar_data(db)
    ui.print_calendar(grid, consistency=score)


def get_trends_data(
    db: Database, days: int, today: date | None = None
) -> list[analytics.TrendPoint]:
    # Metadata only (word counts/goal-met per day) -- private entries count, same as calendar.
    return analytics.trend_series(db.all_entries(), days=days, today=today)


def show_trends(db: Database, days: int) -> None:
    ensure_profile(db)
    ui.print_trends(get_trends_data(db, days))


def get_records_data(db: Database) -> analytics.Records | None:
    profile = db.get_profile()
    if profile is None:
        return None
    # Metadata only (word counts, dates, streaks) -- private entries count, same as calendar.
    return analytics.personal_records(db.all_entries(), profile)


def show_records(db: Database) -> None:
    ensure_profile(db)
    ui.print_records(get_records_data(db))


def get_patterns_data(db: Database) -> analytics.PatternSummary:
    # Metadata only (day/time counts) -- private entries count, same as calendar.
    return analytics.writing_pattern(db.all_entries())


def show_patterns(db: Database) -> None:
    ensure_profile(db)
    ui.print_patterns(get_patterns_data(db))


def get_goal_suggestion(
    db: Database, days: int = 30, today: date | None = None
) -> tuple[int | None, int | None]:
    """Returns (current_goal, suggested_or_None); both None if no profile exists yet."""
    profile = db.get_profile()
    if profile is None:
        return None, None
    # Metadata only (word-count trend) -- private entries count, same as calendar.
    suggestion = analytics.suggest_goal(
        db.all_entries(),
        profile.writing_goal,
        days=days,
        today=today,
    )
    return profile.writing_goal, suggestion


def suggest_goal_action(db: Database) -> None:
    ensure_profile(db)
    current, suggestion = get_goal_suggestion(db)
    ui.print_goal_suggestion(current_goal=current, suggested=suggestion)


def get_streak_data(db: Database) -> tuple[int, int]:
    """Returns (streak, longest_streak); (0, 0) if no profile exists yet."""
    profile = db.get_profile()
    if profile is None:
        return 0, 0
    return profile.streak, profile.longest_streak


def get_current_goal(db: Database) -> int | None:
    profile = db.get_profile()
    return profile.writing_goal if profile else None


def _average_wpm(entries: list[JournalEntry]) -> float:
    wpm_values = [e.words_per_minute for e in entries if e.words_per_minute]
    return round(sum(wpm_values) / len(wpm_values), 2) if wpm_values else 0.0


def get_stats_totals(db: Database) -> StatsTotals:
    """Zero-decryption stats: unlike show_stats, this never lazily unlocks to backfill
    word_count on legacy entries -- it only reads what's already in the DB."""
    total_words, entry_count = db.aggregate_totals()
    avg_wpm = _average_wpm(db.all_entries())
    return StatsTotals(
        total_words=total_words, entry_count=entry_count, avg_words_per_minute=avg_wpm
    )


# --- content-based features (need to decrypt entry text) ---


def get_word_frequency(
    db: Database,
    profile: Profile,
    key: bytes | None,
    entries: list[JournalEntry] | None = None,
    top_n: int = 20,
) -> list[tuple[str, int]]:
    if entries is None:
        entries = filter_private(db.all_entries(), include_private=False)
    decrypted = all_decrypted(db, profile, key, entries=entries)
    return content.word_frequency([e.text for e in decrypted], top_n=top_n)


def show_word_frequency(db: Database) -> None:
    profile, key = ensure_profile(db)
    freq = get_word_frequency(db, profile, key)
    if not freq:
        print("You haven't written anything yet.")
        return
    ui.print_word_frequency(freq)


def get_search_results(
    db: Database,
    profile: Profile,
    key: bytes | None,
    query: str,
    entries: list[JournalEntry] | None = None,
) -> list[tuple[date, str]]:
    if entries is None:
        entries = filter_private(db.all_entries(), include_private=False)
    decrypted = all_decrypted(db, profile, key, entries=entries)
    return content.search_matches(decrypted, query)


def search_journal(db: Database, query: str) -> None:
    profile, key = ensure_profile(db)
    ui.print_search_results(query, get_search_results(db, profile, key, query))


def on_this_day_matches(
    entries: list[JournalEntry], today: date | None = None
) -> list[JournalEntry]:
    """Feb 29 entries are shown on Feb 28 in years that don't have a Feb 29 to match
    against -- otherwise a leap-day entry would only resurface once every 4 years."""
    today = today or date.today()
    include_leap_day = today.month == 2 and today.day == 28 and not calendar.isleap(today.year)
    return [
        e
        for e in entries
        if e.entry_date.year != today.year
        and (
            (e.entry_date.month == today.month and e.entry_date.day == today.day)
            or (include_leap_day and e.entry_date.month == 2 and e.entry_date.day == 29)
        )
    ]


def get_on_this_day(
    db: Database,
    profile: Profile,
    key: bytes | None,
    today: date | None = None,
    entries: list[JournalEntry] | None = None,
) -> list[DecryptedEntry]:
    if entries is None:
        entries = on_this_day_matches(
            filter_private(db.all_entries(), include_private=False), today=today
        )
    return all_decrypted(db, profile, key, entries=entries)


def show_on_this_day(db: Database) -> None:
    profile, key = ensure_profile(db)
    ui.print_on_this_day(get_on_this_day(db, profile, key))


def get_entry_by_date(
    db: Database,
    profile: Profile,
    key: bytes | None,
    entry_date: date,
    include_private: bool = False,
) -> DecryptedEntry | None:
    """Single-entry read. Checks entry.private *before* decrypting, so a private entry
    queried without Tier-3 access never triggers unlock() at all -- preserve this ordering
    under any future refactor, it's a real privacy guarantee, not just style."""
    entry = db.get_entry(entry_date)
    if entry is None:
        return None
    if entry.private and not include_private:
        return None
    decrypted = all_decrypted(db, profile, key, entries=[entry])
    return decrypted[0] if decrypted else None


def set_private(db: Database, entry_date: date, private: bool) -> None:
    entry = db.get_entry(entry_date)
    if entry is None:
        print(f"No entry found for {entry_date.isoformat()}.")
        return
    db.set_private(entry_date, private)
    state = "private" if private else "no longer private"
    print(f"Entry for {entry_date.isoformat()} is now {state}.")


def export_journal(
    db: Database, output_path: Path, export_format: str, include_private: bool = False
) -> None:
    if export_format not in ("md", "json"):
        print("Format must be 'md' or 'json'.")
        return

    profile, key = ensure_profile(db)
    all_entries = db.all_entries()
    if not all_entries:
        print("You haven't written anything yet.")
        return
    entries = filter_private(all_entries, include_private)
    if not entries:
        print("All your entries are private -- pass --include-private to export them anyway.")
        return

    if profile.has_passphrase:
        confirm = (
            input(
                "This journal is encrypted, but the exported file will be plaintext on "
                "disk. Continue? (y/N) -> "
            )
            .strip()
            .lower()
        )
        if confirm != "y":
            print("Export cancelled.")
            return

    decrypted = all_decrypted(db, profile, key, entries=entries)
    if export_format == "md":
        text = content.format_markdown(decrypted)
    else:
        text = content.format_json(decrypted)
    output_path.write_text(text, encoding="utf-8")
    print(f"Exported {len(decrypted)} entries to {output_path}")
