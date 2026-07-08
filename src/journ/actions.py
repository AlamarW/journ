"""Shared verbs used by both the one-shot CLI commands (cli.py) and the REPL (shell.py),
so each behavior has exactly one implementation.
"""

from __future__ import annotations

import getpass
import os
import subprocess
from dataclasses import replace
from datetime import date, datetime

from journ import config, crypto
from journ.db import Database
from journ.models import JournalEntry, Profile
from journ.streak import update_streak
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
            "Set a passphrase to encrypt your entries? Recommended for personal "
            "journals. (y/N) -> "
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


def _decode_entry(entry: JournalEntry, key: bytes | None) -> str:
    if entry.is_encrypted:
        if key is None:
            raise PassphraseError("This entry is encrypted but no passphrase was provided.")
        return crypto.decrypt_text(key, entry.content)
    return entry.content.decode("utf-8")


def _encode_entry(text: str, key: bytes | None) -> tuple[bytes, bool]:
    if key is not None:
        return crypto.encrypt_text(key, text), True
    return text.encode("utf-8"), False


def write_today_entry(db: Database) -> None:
    profile, key = ensure_profile(db)
    if key is None:
        key = unlock(profile)

    today = date.today()
    existing = db.get_entry(today)
    existing_text = _decode_entry(existing, key) if existing else ""

    editor = config.get_editor()
    config.journ_tmp_dir.mkdir(parents=True, exist_ok=True)
    scratch_path = config.journ_tmp_dir / f"{today.isoformat()}.txt"

    for leftover in config.journ_tmp_dir.glob("*.txt"):
        if leftover != scratch_path:
            leftover.unlink()

    scratch_path.write_text(existing_text, encoding="utf-8")

    start_time = datetime.now()
    try:
        subprocess.run(
            config.editor_argv(editor) + [str(scratch_path)],
            shell=(os.name == "nt"),
        )
    except FileNotFoundError:
        scratch_path.unlink(missing_ok=True)
        print(f"Could not launch editor '{editor}'. Set EDITOR to a valid command and try again.")
        return
    elapsed = datetime.now() - start_time

    text = scratch_path.read_text(encoding="utf-8")
    scratch_path.unlink(missing_ok=True)

    word_count = count_words(text)
    goal_met = word_count >= profile.writing_goal
    wpm = words_per_minute(word_count, elapsed)

    if goal_met:
        print(
            f"You've typed {word_count} words. This is over your goal of "
            f"{profile.writing_goal} words!"
        )
    else:
        print(
            f"You've typed {word_count} words. This is under your goal of "
            f"{profile.writing_goal} words"
        )
    print(f"You've journalled for {format_elapsed(elapsed)}")
    print(f"That's {wpm} words per minute")

    content, is_encrypted = _encode_entry(text, key)
    db.upsert_entry(
        JournalEntry(
            entry_date=today,
            content=content,
            is_encrypted=is_encrypted,
            words_per_minute=wpm,
            accomplished_goal=goal_met,
            updated_at=datetime.now().isoformat(),
        )
    )

    new_streak, new_last_entry_date = update_streak(
        profile.streak, profile.streak_last_entry_date, today, goal_met
    )
    db.update_streak(new_streak, new_last_entry_date)
    if new_streak != profile.streak:
        print(f"Your streak is now {new_streak} day(s)!")
    else:
        print(f"Your current streak is {profile.streak} day(s).")


def show_streak(db: Database) -> None:
    profile, _key = ensure_profile(db)
    print(f"Your streak is currently {profile.streak} day(s).")


def show_last_entry(db: Database) -> None:
    profile, key = ensure_profile(db)
    entry = db.latest_entry()
    if entry is None:
        print("You haven't written anything yet.")
        return
    if key is None:
        key = unlock(profile)
    word_count = count_words(_decode_entry(entry, key))
    print(
        f"Your most recent entry ({entry.entry_date.isoformat()}) is {word_count} words; "
        f"your goal is {profile.writing_goal} words."
    )


def show_stats(db: Database) -> None:
    profile, key = ensure_profile(db)
    entries = db.all_entries()
    if not entries:
        print("You haven't written anything yet.")
        return

    if key is None:
        key = unlock(profile)
    total_words = 0
    wpm_values = []
    for entry in entries:
        total_words += count_words(_decode_entry(entry, key))
        if entry.words_per_minute:
            wpm_values.append(entry.words_per_minute)

    avg_wpm = round(sum(wpm_values) / len(wpm_values), 2) if wpm_values else 0.0
    print(f"Your average words per minute is {avg_wpm}")
    print(f"You've written a total of {total_words} words across {len(entries)} entries!")


def set_goal(db: Database, new_goal: int | None) -> None:
    profile, _key = ensure_profile(db)
    if new_goal is None:
        print(f"Your current daily writing goal is {profile.writing_goal} words.")
        return
    db.update_goal(new_goal)
    print(f"Daily writing goal updated to {new_goal} words.")


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
        text = _decode_entry(entry, old_key)
        content, is_encrypted = _encode_entry(text, new_key)
        db.upsert_entry(replace(entry, content=content, is_encrypted=is_encrypted))
    db.set_passphrase(new_salt, new_canary)
