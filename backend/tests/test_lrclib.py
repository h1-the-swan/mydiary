# -*- coding: utf-8 -*-

from unittest.mock import patch

import pytest
import requests

from mydiary import lrclib_connector
from mydiary.lrclib_connector import LrclibLyrics, fetch_lyrics

LYRICS = "Paper lanterns on the line\nHold the light\n\nHold the light"


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


def record(duration=200.0, plain=LYRICS, artist="The Invented Band", instrumental=False):
    return {
        "trackName": "Paper Lanterns",
        "artistName": artist,
        "duration": duration,
        "plainLyrics": plain,
        "instrumental": instrumental,
    }


def routed(get_response, search_response):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert "mydiary" in headers["User-Agent"]
        return get_response if url.endswith("/get") else search_response

    return fake_get


class TestFetchLyrics:
    def test_exact_get_match(self):
        with patch.object(lrclib_connector.requests, "get", side_effect=routed(FakeResponse(200, record()), None)):
            found = fetch_lyrics("Paper Lanterns", "The Invented Band", 200.4)
        assert found == LrclibLyrics("Paper Lanterns", "The Invented Band", 200.0, LYRICS)

    def test_falls_back_to_search_closest_duration(self):
        results = [record(duration=320.0, plain="long version"), record(duration=199.0)]
        with patch.object(
            lrclib_connector.requests, "get",
            side_effect=routed(FakeResponse(404, {}), FakeResponse(200, results)),
        ):
            found = fetch_lyrics("Paper Lanterns", "The Invented Band", 200.0)
        assert found.duration == 199.0

    def test_search_without_duration_prefers_matching_artist(self):
        results = [record(artist="A Cover Band", plain="cover"), record()]
        with patch.object(lrclib_connector.requests, "get", side_effect=routed(None, FakeResponse(200, results))):
            found = fetch_lyrics("Paper Lanterns", "The Invented Band", None)
        assert found.plain_lyrics == LYRICS

    def test_skips_instrumental_and_empty(self):
        results = [record(instrumental=True), record(plain="")]
        with patch.object(lrclib_connector.requests, "get", side_effect=routed(None, FakeResponse(200, results))):
            assert fetch_lyrics("Paper Lanterns", "The Invented Band") is None

    def test_server_error_raises(self):
        with patch.object(lrclib_connector.requests, "get", side_effect=routed(None, FakeResponse(500, {}))):
            with pytest.raises(requests.HTTPError):
                fetch_lyrics("Paper Lanterns", "The Invented Band")


@pytest.mark.external_api
def test_live_lookup():
    # a real request, but only the shape is checked -- no lyrics are asserted
    found = fetch_lyrics("Bohemian Rhapsody", "Queen")
    assert found is not None and found.plain_lyrics
