# -*- coding: utf-8 -*-

DESCRIPTION = """Turn a day's missed Spelling Bee words back into a playable hive.

The NYT Spelling Bee gives you seven letters, one of them mandatory, and every
valid word is built from those seven. That constraint runs backwards: the union
of the letters across a day's words is always a subset of the real seven, and
the mandatory centre letter appears in every one of them, so it must be in their
intersection. A hive can therefore be reconstructed from nothing but the words
themselves -- recording the actual letters makes it exact, but is optional.

Any centre drawn from that intersection is safe to play on. It is in every
target word by construction, so a "wrong" pick only mislabels which hex is
highlighted; it can never make one of the day's words impossible to enter.

This module is pure functions over word lists -- no network, no database, no
rendering -- so the derivation can be tested on its own."""

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Iterable, List, Optional, Sequence, Set, Tuple

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


# the Bee never accepts words shorter than this
MIN_WORD_LEN = 4
# a hive is always seven letters: one centre, six outer
HIVE_SIZE = 7
VOWELS = "AEIOU"

# letters to draw on when the day's words don't account for all seven. roughly
# frequency-ordered, so a padded board looks like a plausible puzzle.
PAD_POOL = "AEIOULNTRCDGMPBHKFVWYJXQZ"
# S is vanishingly rare in real puzzles, so guessing it is almost always wrong.
# this applies to padding ONLY -- an S in a recorded word or in recorded letters
# is perfectly legitimate and is never filtered out.
PAD_EXCLUDE = "S"

_NON_ALPHA = re.compile(r"[^A-Z]")
_SPLIT = re.compile(r"[\s,;]+")


@dataclass(frozen=True)
class HiveLetters:
    """A reconstructed hive, plus how much of it we actually know."""

    puzzle_date: date
    center_letter: str
    outer_letters: Tuple[str, ...]
    # True only when the letters came from a recorded puzzle. False means they
    # were worked out from the words, which is usually right but not certain.
    exact: bool
    words: Tuple[str, ...]
    pangrams: Tuple[str, ...]
    warnings: Tuple[str, ...]

    @property
    def letters(self) -> Set[str]:
        return {self.center_letter} | set(self.outer_letters)


def normalize_word(word: str) -> str:
    """Uppercase, stripped of anything that isn't a letter."""
    return _NON_ALPHA.sub("", (word or "").strip().upper())


def parse_words(blob: str) -> List[str]:
    """Split a pasted answer list into normalized words, keeping paste order.

    The NYT "Yesterday's Answers" list copies as one word per line, but people
    also type them separated by spaces or commas, so accept all three.
    """
    seen = set()
    out = []
    for chunk in _SPLIT.split(blob or ""):
        word = normalize_word(chunk)
        if word and word not in seen:
            seen.add(word)
            out.append(word)
    return out


def is_pangram(word: str) -> bool:
    """A word using all seven letters. Since a puzzle only has seven, any valid
    word with seven distinct letters is necessarily a pangram."""
    return len(set(normalize_word(word))) == HIVE_SIZE


def validate_words(words: Iterable[str]) -> Tuple[List[str], List[str]]:
    """Split input into (valid, invalid), preserving order and dropping repeats.

    Invalid entries are returned in their original form so the caller can show
    the user what it rejected.
    """
    valid: List[str] = []
    invalid: List[str] = []
    seen = set()
    for raw in words or []:
        # punctuation is stripped rather than rejected -- pasted lists pick up
        # stray commas, and the entry form shows the user what it parsed anyway
        word = normalize_word(raw)
        if len(word) < MIN_WORD_LEN:
            invalid.append(raw)
            continue
        if word in seen:
            continue
        seen.add(word)
        valid.append(word)
    return valid, invalid


def _deterministic_order(items: Iterable[str], seed: str) -> List[str]:
    """Shuffle stably from a seed.

    Python's hash() is salted by PYTHONHASHSEED, so it would reorder the board
    on every backend restart. Hashing explicitly keeps a given day's hive
    looking the same every time it is opened.
    """
    return sorted(
        items, key=lambda c: hashlib.md5(f"{seed}|{c}".encode("utf-8")).hexdigest()
    )


def _pad_letters(used: Set[str], seed: str) -> List[str]:
    """Fill a short letter set out to seven with plausible spares."""
    pool = [c for c in PAD_POOL if c not in used and c not in PAD_EXCLUDE]
    padding = _deterministic_order(pool, seed)[: HIVE_SIZE - len(used)]
    letters = sorted(used | set(padding))
    # a hive with no vowel can't spell anything; swap one of ours in
    if not any(c in VOWELS for c in letters):
        spare = [c for c in VOWELS if c not in letters]
        if spare and padding:
            letters.remove(padding[-1])
            letters.append(_deterministic_order(spare, seed)[0])
            letters.sort()
    return letters


def _choose_center(words: Sequence[str], letters: Set[str], seed: str) -> Tuple[str, List[str]]:
    """Pick the mandatory letter, preferring one that is in every word."""
    warnings: List[str] = []
    common = set(letters)
    for word in words:
        common &= set(word)
    if common:
        return _deterministic_order(common, seed)[0], warnings
    # no letter shared by every word means the words can't be from one puzzle
    warnings.append(
        "No letter appears in every word, so these words probably aren't all "
        "from the same puzzle. Guessing the most common letter as the centre."
    )
    counts = Counter(c for word in words for c in set(word))
    best = max(counts.values())
    return _deterministic_order([c for c, n in counts.items() if n == best], seed)[0], warnings


def derive_hive(
    puzzle_date: date,
    words: Sequence[str],
    center_letter: Optional[str] = None,
    outer_letters: Optional[str] = None,
) -> HiveLetters:
    """Reconstruct the day's hive from its words, and its letters if recorded.

    Precedence for the seven letters: recorded letters, then a pangram among the
    words (which pins the set exactly, since a pangram uses all seven), then the
    union of the words padded out.
    """
    words = [w for w in (normalize_word(w) for w in words or []) if w]
    seed = puzzle_date.isoformat()
    warnings: List[str] = []
    exact = False

    stored = _stored_letters(center_letter, outer_letters)
    used: Set[str] = set().union(*(set(w) for w in words)) if words else set()

    if stored:
        letters = stored
        exact = True
    else:
        pangram = next((w for w in words if is_pangram(w)), None)
        if pangram:
            # a pangram uses all seven, so its letters ARE the puzzle's
            letters = set(pangram)
        elif len(used) > HIVE_SIZE:
            warnings.append(
                f"These words use {len(used)} distinct letters, but a Spelling "
                f"Bee puzzle only has {HIVE_SIZE}. Some of them are probably "
                f"typos, or from a different day."
            )
            # keep the letters used by the most words; ties broken by letter so
            # the board doesn't depend on the order the words arrived in
            counts = Counter(c for word in words for c in set(word))
            ranked = sorted(counts, key=lambda c: (-counts[c], c))
            letters = set(ranked[:HIVE_SIZE])
        else:
            letters = set(_pad_letters(used, seed))

    if len(words) < 3:
        warnings.append(
            "Only a word or two recorded for this day, so the centre letter is "
            "a guess."
        )

    stored_center = normalize_word(center_letter or "")
    if stored and stored_center in letters:
        # recorded centre always wins; nothing to infer
        center = stored_center
    elif words:
        center, center_warnings = _choose_center(words, letters, seed)
        warnings.extend(center_warnings)
    else:
        center = _deterministic_order(letters, seed)[0]

    # keep only what's actually playable on this board, so the game can never
    # ask for a word the hive can't spell
    playable = [w for w in words if set(w) <= letters and center in w]
    dropped = len(words) - len(playable)
    if dropped:
        warnings.append(
            f"{dropped} recorded word{'s' if dropped > 1 else ''} can't be made "
            f"from these letters and won't appear in the game."
        )

    outer = tuple(sorted(letters - {center}))
    return HiveLetters(
        puzzle_date=puzzle_date,
        center_letter=center,
        outer_letters=outer,
        exact=exact,
        words=tuple(playable),
        pangrams=tuple(w for w in playable if is_pangram(w)),
        warnings=tuple(warnings),
    )


def _stored_letters(
    center_letter: Optional[str], outer_letters: Optional[str]
) -> Optional[Set[str]]:
    """The recorded seven, if they were recorded and make sense."""
    center = normalize_word(center_letter or "")
    outer = normalize_word(outer_letters or "")
    if len(center) != 1 or len(outer) != HIVE_SIZE - 1:
        return None
    letters = {center} | set(outer)
    if len(letters) != HIVE_SIZE:
        return None
    return letters
