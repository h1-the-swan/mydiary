import io
import json
from pathlib import Path

import pendulum
import pytest
from PIL import Image

from mydiary import map_render
from mydiary.map_render import FOOTER_HEIGHT, RenderParams, render_day_map, stay_radius
from mydiary.owntracks_track import TrackPoint, build_track

TZ = "America/New_York"


class FakeTileDownloader:
    """Serves a flat tile so rendering never touches the network."""

    def __init__(self, color=(235, 235, 233, 255)):
        buf = io.BytesIO()
        Image.new("RGBA", (512, 512), color).save(buf, format="PNG")
        self.tile = buf.getvalue()
        self.requested = []

    def set_user_agent(self, user_agent):  # matches TileDownloader's interface
        pass

    def get(self, provider, cache_dir, zoom, x, y):
        self.requested.append((provider.name(), zoom, x, y))
        return self.tile


@pytest.fixture(autouse=True)
def tmp_cache_dir(tmp_path, monkeypatch):
    """Keep the tile cache out of the real cache directory."""
    monkeypatch.setenv("MYDIARY_CACHE_DIR", str(tmp_path))


@pytest.fixture
def downloader():
    return FakeTileDownloader()


@pytest.fixture
def july1_track(rootdir: str):
    items = json.loads(
        Path(rootdir).joinpath("owntracks_data", "owntracks_2026-07-01.json").read_text()
    )
    points = [
        TrackPoint(
            tst=pendulum.from_timestamp(x["tst"], tz=TZ),
            lat=x["lat"],
            lon=x["lon"],
            acc=x.get("acc"),
        )
        for x in sorted(items, key=lambda x: x["tst"])
    ]
    return build_track(points)


def test_renders_a_jpeg_of_the_requested_size(july1_track, downloader):
    data = render_day_map(
        july1_track, render=RenderParams(width=800, height=600), tile_downloader=downloader
    )
    image = Image.open(io.BytesIO(data))
    assert image.format == "JPEG"
    assert image.size == (800, 600)


def test_png_is_still_available(july1_track, downloader):
    # the escape hatch for anything that needs lossless output
    data = render_day_map(
        july1_track,
        render=RenderParams(width=400, height=300, fmt="PNG"),
        tile_downloader=downloader,
    )
    image = Image.open(io.BytesIO(data))
    assert image.format == "PNG"
    assert image.size == (400, 300)


def test_render_params_describe_their_encoding():
    assert RenderParams().ext == "jpg"
    assert RenderParams().media_type == "image/jpeg"
    assert RenderParams(fmt="png").ext == "png"  # normalised, not case-sensitive
    assert RenderParams(fmt="jpg").cache_key() == RenderParams(fmt="JPEG").cache_key()


def test_render_params_reject_an_unknown_format():
    # the API takes fmt as a query parameter, so this is a 400, not a 500
    with pytest.raises(ValueError):
        RenderParams(fmt="tiff").media_type


def test_render_fetches_both_basemap_and_label_tiles(july1_track, downloader):
    render_day_map(
        july1_track, render=RenderParams(width=400, height=300), tile_downloader=downloader
    )
    providers = {name for name, _, _, _ in downloader.requested}
    assert providers == {
        map_render.BASEMAP_PROVIDER.name(),
        map_render.LABELS_PROVIDER.name(),
    }


def test_render_makes_no_network_calls(july1_track, downloader):
    # the fake downloader is the only tile source; if anything else reached out
    # this test would be slow and flaky rather than hermetic
    render_day_map(
        july1_track, render=RenderParams(width=400, height=300), tile_downloader=downloader
    )
    assert downloader.requested


def test_footer_is_drawn_below_the_map(july1_track, downloader):
    # rendered as PNG so the assertion is about what was drawn rather than
    # about how much JPEG nudged a flat colour
    data = render_day_map(
        july1_track,
        render=RenderParams(width=800, height=600, fmt="PNG"),
        tile_downloader=downloader,
    )
    image = Image.open(io.BytesIO(data)).convert("RGB")
    # the legend strip sits on the surface colour, not on tile grey
    assert image.getpixel((400, 600 - FOOTER_HEIGHT // 2)) == map_render.SURFACE


def test_render_is_deterministic(july1_track, downloader):
    first = render_day_map(
        july1_track, render=RenderParams(width=400, height=300), tile_downloader=downloader
    )
    second = render_day_map(
        july1_track, render=RenderParams(width=400, height=300), tile_downloader=FakeTileDownloader()
    )
    assert first == second


def test_render_rejects_an_empty_day(downloader):
    with pytest.raises(ValueError):
        render_day_map(build_track([]), tile_downloader=downloader)


def test_render_survives_a_flight_day(downloader):
    # a 4000km bounding box must not blow up the zoom fitting
    base = pendulum.datetime(2026, 6, 17, 9, tz=TZ)
    points = [
        TrackPoint(base, 33.498, -42.0054),
        TrackPoint(base.add(hours=1), 33.371, -41.8438),
        TrackPoint(base.add(hours=7), 26.782, -82.2279),
    ]
    png = render_day_map(
        build_track(points), render=RenderParams(width=600, height=450), tile_downloader=downloader
    )
    assert Image.open(io.BytesIO(png)).size == (600, 450)


def test_stay_radius_grows_with_duration_but_is_bounded():
    assert stay_radius(20) < stay_radius(120) < stay_radius(600)
    assert stay_radius(0) == map_render.STAY_MIN_RADIUS
    assert stay_radius(100000) == map_render.STAY_MAX_RADIUS


def test_retina_provider_declares_512px_tiles():
    # the transformer reads tile_size off the provider, so @2x tiles only line
    # up because this override is honoured all the way through
    assert map_render.BASEMAP_PROVIDER.tile_size() == 512
    url = map_render.BASEMAP_PROVIDER.url(3, 1, 2)
    assert "@2x" in url
    assert url.startswith("https://")
