# -*- coding: utf-8 -*-

DESCRIPTION = """Look up what a missed Spelling Bee word actually means.

Half the reason a word gets missed is that it isn't in your vocabulary, so the
definition is the most useful hint the practice drill has. Uses the free
dictionaryapi.dev, which has no key and no SLA -- so lookups are on demand only,
and the caller caches the result (including "no definition found", which is a
perfectly normal answer for the obscure words the Bee likes)."""

from typing import Optional, Tuple

import requests

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en"
# how many senses to keep. one is usually too terse to be a useful hint; more
# than two turns the drill's hint panel into an essay.
MAX_SENSES = 2
# a free service with no SLA, and these routes are sync, so a hang would pin a
# worker thread rather than just being slow
DEFAULT_TIMEOUT = 10


def fetch_definition(
    word: str, timeout: int = DEFAULT_TIMEOUT
) -> Tuple[Optional[str], Optional[str]]:
    """Look up a word.

    Returns (definition, part_of_speech). (None, None) means the lookup
    succeeded but the word isn't in the dictionary -- worth caching, so it
    isn't asked again.
    """
    word = (word or "").strip()
    if not word:
        return None, None

    resp = requests.get(f"{DICTIONARY_API_URL}/{word.lower()}", timeout=timeout)
    if resp.status_code == 404:
        logger.debug("no dictionary entry for %s", word)
        return None, None
    resp.raise_for_status()

    return _parse_entries(resp.json())


def _parse_entries(payload) -> Tuple[Optional[str], Optional[str]]:
    """Flatten the API's nested entry list to a sentence or two.

    Stored as plain text rather than raw JSON: there's no JSON column anywhere
    in this database, and the UI only ever displays it.
    """
    if not isinstance(payload, list) or not payload:
        return None, None
    meanings = payload[0].get("meanings") or []
    if not meanings:
        return None, None

    meaning = meanings[0]
    part_of_speech = meaning.get("partOfSpeech")
    senses = [
        d.get("definition")
        for d in (meaning.get("definitions") or [])
        if d.get("definition")
    ]
    if not senses:
        return None, part_of_speech
    return " ".join(s.rstrip(".") + "." for s in senses[:MAX_SENSES]), part_of_speech
