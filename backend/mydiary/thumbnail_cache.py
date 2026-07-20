# -*- coding: utf-8 -*-

DESCRIPTION = """Disk cache for Nextcloud photo thumbnails.

Photo filenames embed their capture timestamp, so a given (path, size) is
immutable: there is no invalidation. Delete the cache directory to reset."""

import hashlib
import os
from pathlib import Path
from typing import Optional

from requests.utils import unquote

from .db import rootdir


def get_cache_dir() -> Path:
    cache_dir = (
        Path(os.getenv("MYDIARY_CACHE_DIR") or os.path.join(rootdir, ".cache"))
        / "nextcloud_thumbnails"
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def cache_key(nextcloud_path: str, w: int = 512, h: int = 512) -> str:
    return hashlib.sha256(f"{unquote(nextcloud_path)}|{w}x{h}".encode()).hexdigest()


def get_cached(key: str) -> Optional[bytes]:
    filepath = get_cache_dir() / f"{key}.img"
    if filepath.exists():
        return filepath.read_bytes()
    return None


def store(key: str, data: bytes) -> None:
    cache_dir = get_cache_dir()
    tmp_path = cache_dir / f"{key}.tmp"
    tmp_path.write_bytes(data)
    os.replace(tmp_path, cache_dir / f"{key}.img")


def sniff_media_type(data: bytes) -> str:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return "image/png"
