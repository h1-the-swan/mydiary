# -*- coding: utf-8 -*-

DESCRIPTION = """Look up a song's plain lyrics on LRCLIB (lrclib.net).

LRCLIB is open data with no key. It asks clients to identify themselves in the
User-Agent. `/api/get` matches on track, artist and duration and returns one
record or 404; `/api/search` is the looser fallback. Lookups are on demand only
(starting a sheet), and nothing is cached: the lyrics end up in the sheet the
user edits."""

from dataclasses import dataclass
from typing import List, Optional

import requests

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

LRCLIB_API_URL = "https://lrclib.net/api"
USER_AGENT = "mydiary (https://github.com/h1-the-swan/mydiary)"
# the route calling this is sync, so a hang would pin a worker thread
DEFAULT_TIMEOUT = 10


@dataclass
class LrclibLyrics:
    track_name: str
    artist_name: str
    duration: Optional[float]  # seconds
    plain_lyrics: str


def _usable(record: dict) -> bool:
    return bool(record.get("plainLyrics")) and not record.get("instrumental")


def _to_lyrics(record: dict) -> LrclibLyrics:
    duration = record.get("duration")
    return LrclibLyrics(
        track_name=record.get("trackName") or "",
        artist_name=record.get("artistName") or "",
        duration=float(duration) if duration is not None else None,
        plain_lyrics=record["plainLyrics"],
    )


def _pick(records: List[dict], artist_name: Optional[str], duration_s: Optional[float]) -> Optional[dict]:
    usable = [r for r in records if _usable(r)]
    if artist_name:
        # search matches covers too; the artist's own recording wins when there is one
        same_artist = [
            r for r in usable if (r.get("artistName") or "").lower() == artist_name.lower()
        ]
        usable = same_artist or usable
    if not usable:
        return None
    if duration_s is not None:
        return min(usable, key=lambda r: abs(float(r.get("duration") or 0) - duration_s))
    return usable[0]


def fetch_lyrics(
    track_name: str,
    artist_name: Optional[str],
    duration_s: Optional[float] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Optional[LrclibLyrics]:
    """Plain lyrics for a song, or None if LRCLIB has none usable."""
    headers = {"User-Agent": USER_AGENT}
    if artist_name and duration_s is not None:
        resp = requests.get(
            f"{LRCLIB_API_URL}/get",
            params={
                "track_name": track_name,
                "artist_name": artist_name,
                "duration": round(duration_s),
            },
            headers=headers,
            timeout=timeout,
        )
        if resp.status_code == 200 and _usable(resp.json()):
            return _to_lyrics(resp.json())
        if resp.status_code not in (200, 404):
            resp.raise_for_status()

    params = {"track_name": track_name}
    if artist_name:
        params["artist_name"] = artist_name
    resp = requests.get(
        f"{LRCLIB_API_URL}/search", params=params, headers=headers, timeout=timeout
    )
    resp.raise_for_status()
    picked = _pick(resp.json() or [], artist_name, duration_s)
    if picked is None:
        logger.debug("no usable LRCLIB lyrics for %s / %s", track_name, artist_name)
        return None
    return _to_lyrics(picked)
