# -*- coding: utf-8 -*-

DESCRIPTION = """Draw a day's movement as a PNG.

py-staticmaps handles the parts that are the same for any map -- fitting the
bounds, picking a zoom, fetching and caching tiles -- and this module supplies
the encoding that makes the day readable:

  * the track is coloured by time of day, in four named periods
  * places the day paused become circles sized by how long
  * links across a long gap are dashed, because the route is genuinely unknown

Drawn at 2x and downscaled, which is where the antialiasing comes from:
PIL.ImageDraw has none of its own."""

import io
import math
from typing import List, Optional, Sequence, Tuple

import s2sphere
import staticmaps
from PIL import Image, ImageDraw, ImageFont
from staticmaps.tile_provider import TileProvider

from . import thumbnail_cache
from .owntracks_track import (
    PERIOD_LABELS,
    DayTrack,
    Link,
    Stay,
    TrackParams,
    summary_label,
)

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


USER_AGENT = "mydiary/1.0 (personal diary; https://github.com/h1-the-swan/mydiary)"
ATTRIBUTION = "© OpenStreetMap contributors © CARTO"

# rendered at this multiple of the requested size, then downscaled
SUPERSAMPLE = 2

SURFACE = (250, 250, 249)
INK = (60, 60, 58)
MUTED = (120, 119, 115)

# all in final-output pixels; the overlay scales them by SUPERSAMPLE
LINE_WIDTH = 2
STAY_MIN_RADIUS = 8
STAY_MAX_RADIUS = 40
STAY_RADIUS_K = 2.2  # radius = K * sqrt(minutes)
STAY_FILL_ALPHA = 56  # ~22%
STAY_STROKE_ALPHA = 217  # ~85%
DASH_ALPHA = 102  # ~40%
DASH_ON = 7
DASH_OFF = 6
LABEL_MIN_MINUTES = 60
FOOTER_HEIGHT = 34


class RetinaTileProvider(TileProvider):
    """A CARTO basemap at 2x pixel density.

    tile_size flows from the provider through the Transformer into the renderer,
    so declaring 512 here is all it takes for @2x tiles to line up.
    """

    def __init__(self, name: str, layer: str) -> None:
        super().__init__(
            name=name,
            url_pattern=(
                "https://$s.basemaps.cartocdn.com/rastertiles/" + layer + "/$z/$x/$y@2x.png"
            ),
            shards=["a", "b", "c", "d"],
            attribution=None,  # drawn in the footer instead, at a legible size
            max_zoom=20,
        )

    @staticmethod
    def tile_size() -> int:
        return 512


# quiet enough to sit under a track; the default OSM style is not
BASEMAP_PROVIDER = RetinaTileProvider("carto-light-nolabels-2x", "light_nolabels")
LABELS_PROVIDER = RetinaTileProvider("carto-light-onlylabels-2x", "light_only_labels")


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _font(size: int) -> ImageFont.ImageFont:
    # Pillow >= 10.1 returns a scalable TrueType-backed default, so the fontless
    # python base image is not a problem
    return ImageFont.load_default(size=size)


class TrackOverlay(staticmaps.Object):
    """Draws the day onto the map, in map pixel space."""

    def __init__(self, track: DayTrack, scale: int = SUPERSAMPLE) -> None:
        super().__init__()
        self.track = track
        self.scale = scale

    def bounds(self) -> s2sphere.LatLngRect:
        return bounds_for(self.track)

    def extra_pixel_bounds(self):
        # keep the biggest dwell circle from being clipped at the edge
        margin = int((STAY_MAX_RADIUS + 6) * self.scale)
        return margin, margin, margin, margin

    def render_pillow(self, renderer) -> None:
        trans = renderer.transformer()
        overlay = Image.new("RGBA", renderer.image().size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        off = renderer.offset_x()

        def to_px(lat: float, lon: float) -> Tuple[float, float]:
            x, y = trans.ll2pixel(s2sphere.LatLng.from_degrees(lat, lon))
            return x + off, y

        for link in self.track.links:
            self._draw_link(draw, link, to_px)
        for stay in self.track.stays:
            self._draw_stay(draw, stay, to_px)

        renderer.alpha_compose(overlay)

        # labels go on the composited image so their halo reads against the map
        label_draw = ImageDraw.Draw(renderer.image())
        for stay in self.track.stays:
            self._draw_stay_label(label_draw, stay, to_px)

    def _draw_link(self, draw, link: Link, to_px) -> None:
        color = _hex_to_rgb(link.period.color)
        width = max(1, int(LINE_WIDTH * self.scale))
        start = to_px(link.start_lat, link.start_lon)
        end = to_px(link.end_lat, link.end_lon)
        if link.uncertain:
            _dashed_line(
                draw,
                start,
                end,
                fill=color + (DASH_ALPHA,),
                width=width,
                dash_on=DASH_ON * self.scale,
                dash_off=DASH_OFF * self.scale,
            )
            return
        draw.line([start, end], fill=color + (255,), width=width)
        # round off the joins, which ImageDraw does not do for us
        for point in (start, end):
            _dot(draw, point, width / 2, color + (255,))

    def _draw_stay(self, draw, stay: Stay, to_px) -> None:
        color = _hex_to_rgb(stay.period.color)
        center = to_px(stay.lat, stay.lon)
        radius = stay_radius(stay.duration_minutes) * self.scale
        # a surface ring first, so the circle separates from the track beneath
        _ring(draw, center, radius + 1.5 * self.scale, SURFACE + (200,), 3 * self.scale)
        _disc(draw, center, radius, color + (STAY_FILL_ALPHA,))
        _ring(draw, center, radius, color + (STAY_STROKE_ALPHA,), 2 * self.scale)

    def _draw_stay_label(self, draw, stay: Stay, to_px) -> None:
        if stay.duration_minutes < LABEL_MIN_MINUTES:
            return  # selective labels only, never one on every mark
        center = to_px(stay.lat, stay.lon)
        radius = stay_radius(stay.duration_minutes) * self.scale
        draw.text(
            (center[0], center[1] + radius + 3 * self.scale),
            stay.duration_label(),
            font=_font(11 * self.scale),
            fill=INK,
            stroke_width=max(1, self.scale),
            stroke_fill=SURFACE,
            anchor="ma",
        )


class LabelsOverlay(staticmaps.Object):
    """Street names, composited last so they stay readable over the track."""

    def __init__(self, cache_dir: str) -> None:
        super().__init__()
        self.cache_dir = cache_dir
        self.downloader = staticmaps.TileDownloader()
        self.downloader.set_user_agent(USER_AGENT)

    def bounds(self) -> s2sphere.LatLngRect:
        return s2sphere.LatLngRect()

    def extra_pixel_bounds(self):
        return 0, 0, 0, 0

    def render_pillow(self, renderer) -> None:
        trans = renderer.transformer()
        overlay = Image.new("RGBA", renderer.image().size, (0, 0, 0, 0))
        size = trans.tile_size()
        for yy in range(trans.tiles_y()):
            y = trans.first_tile_y() + yy
            if y < 0 or y >= trans.number_of_tiles():
                continue
            for xx in range(trans.tiles_x()):
                x = (trans.first_tile_x() + xx) % trans.number_of_tiles()
                try:
                    data = self.downloader.get(
                        LABELS_PROVIDER, self.cache_dir, trans.zoom(), x, y
                    )
                except Exception as e:  # a missing label tile must not fail the map
                    logger.warning(f"could not fetch label tile {trans.zoom()}/{x}/{y}: {e}")
                    continue
                if data is None:
                    continue
                tile = Image.open(io.BytesIO(data)).convert("RGBA")
                overlay.paste(
                    tile,
                    (
                        int(xx * size + trans.tile_offset_x()),
                        int(yy * size + trans.tile_offset_y()),
                    ),
                    tile,
                )
        renderer.alpha_compose(overlay)


def stay_radius(minutes: float) -> float:
    """Circle radius in output pixels. sqrt keeps a 6-hour stay from dwarfing a
    20-minute one."""
    return min(STAY_MAX_RADIUS, max(STAY_MIN_RADIUS, STAY_RADIUS_K * math.sqrt(max(minutes, 0))))


def _dot(draw, center, radius, fill) -> None:
    x, y = center
    draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=fill)


def _disc(draw, center, radius, fill) -> None:
    _dot(draw, center, radius, fill)


def _ring(draw, center, radius, color, width) -> None:
    x, y = center
    draw.ellipse(
        [x - radius, y - radius, x + radius, y + radius],
        outline=color,
        width=max(1, int(width)),
    )


def _dashed_line(draw, start, end, fill, width, dash_on, dash_off) -> None:
    x0, y0 = start
    x1, y1 = end
    length = math.hypot(x1 - x0, y1 - y0)
    if length == 0:
        return
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    pos = 0.0
    while pos < length:
        seg_end = min(pos + dash_on, length)
        draw.line(
            [
                (x0 + ux * pos, y0 + uy * pos),
                (x0 + ux * seg_end, y0 + uy * seg_end),
            ],
            fill=fill,
            width=int(width),
        )
        pos = seg_end + dash_off


def _crop_box(
    ctx: "staticmaps.Context",
    track: DayTrack,
    render_w: int,
    render_h: int,
    aspect: float,
) -> Optional[Tuple[int, int, int, int]]:
    """Where to crop the rendered map so the day fills the frame.

    Zoom is an integer, so the fitted zoom often leaves the track using barely
    half the width -- one level in would not fit at all. Cropping to the content
    afterwards recovers the difference and gives effectively fractional zoom.
    """
    center, zoom = ctx.determine_center_zoom(render_w, render_h)
    if center is None or zoom is None:
        return None
    trans = staticmaps.Transformer(
        render_w, render_h, zoom, center, BASEMAP_PROVIDER.tile_size()
    )
    xs: List[float] = []
    ys: List[float] = []
    for lat, lon in _track_coords(track):
        x, y = trans.ll2pixel(s2sphere.LatLng.from_degrees(lat, lon))
        xs.append(x)
        ys.append(y)
    if not xs:
        return None

    pad = (STAY_MAX_RADIUS + 12) * SUPERSAMPLE
    left, right = min(xs) - pad, max(xs) + pad
    top, bottom = min(ys) - pad, max(ys) + pad

    # never upscale: a day spent entirely in one place should not be zoomed
    # into a blur
    width = max(right - left, render_w / SUPERSAMPLE)
    height = max(bottom - top, render_h / SUPERSAMPLE)
    if width / height < aspect:
        width = height * aspect
    else:
        height = width / aspect

    cx, cy = (left + right) / 2, (top + bottom) / 2
    left, top = cx - width / 2, cy - height / 2
    # keep the crop inside the rendered image
    left = min(max(left, 0), max(render_w - width, 0))
    top = min(max(top, 0), max(render_h - height, 0))
    right = min(left + width, render_w)
    bottom = min(top + height, render_h)
    return int(left), int(top), int(right), int(bottom)


def _track_coords(track: DayTrack) -> List[Tuple[float, float]]:
    coords = [(s.lat, s.lon) for s in track.stays]
    for link in track.links:
        coords.append((link.start_lat, link.start_lon))
        coords.append((link.end_lat, link.end_lon))
    return coords


def bounds_for(track: DayTrack) -> s2sphere.LatLngRect:
    b = track.bounds()
    if b is None:
        raise ValueError("cannot compute bounds for an empty track")
    min_lat, min_lon, max_lat, max_lon = b
    return s2sphere.LatLngRect.from_point_pair(
        s2sphere.LatLng.from_degrees(min_lat, min_lon),
        s2sphere.LatLng.from_degrees(max_lat, max_lon),
    )


def _draw_footer(image: Image.Image, track: DayTrack, width: int, top: int) -> None:
    """Legend strip: the four periods, the day's summary, and attribution.

    The legend is what discharges the contrast relief rule for the lighter
    period colours -- identity is never carried by colour alone.
    """
    draw = ImageDraw.Draw(image)
    draw.rectangle([(0, top), (width, top + FOOTER_HEIGHT)], fill=SURFACE)
    draw.line([(0, top), (width, top)], fill=(230, 229, 226), width=1)

    font = _font(11)
    swatch = 8
    x = 10
    mid = top + FOOTER_HEIGHT // 2
    for period, hours in PERIOD_LABELS:
        color = _hex_to_rgb(period.color)
        draw.ellipse(
            [x, mid - swatch // 2, x + swatch, mid + swatch // 2], fill=color
        )
        x += swatch + 5
        text = f"{period.name} {hours}"
        draw.text((x, mid), text, font=font, fill=INK, anchor="lm")
        x += int(draw.textlength(text, font=font)) + 14

    summary = summary_label(track)
    if track.num_dropped:
        summary += f" · {track.num_dropped} noisy fix{'es' if track.num_dropped > 1 else ''} dropped"
    draw.text((width - 10, mid - 6), summary, font=font, fill=INK, anchor="rm")
    draw.text((width - 10, mid + 7), ATTRIBUTION, font=_font(9), fill=MUTED, anchor="rm")


def render_day_map(
    track: DayTrack,
    params: Optional[TrackParams] = None,
    width: int = 1200,
    height: int = 900,
    tile_downloader=None,
) -> bytes:
    """Render a day's track to PNG bytes.

    tile_downloader is only for tests; leaving it None uses the real, cached one.
    """
    if track.is_empty():
        raise ValueError("cannot render a map for a day with no location data")

    cache_dir = str(thumbnail_cache.get_cache_dir(subdir="map_tiles"))
    map_height = height - FOOTER_HEIGHT

    ctx = staticmaps.Context()
    ctx.set_tile_provider(BASEMAP_PROVIDER)
    ctx.set_cache_dir(cache_dir)
    if tile_downloader is None:
        downloader = staticmaps.TileDownloader()
        downloader.set_user_agent(USER_AGENT)
    else:
        downloader = tile_downloader
    ctx.set_tile_downloader(downloader)
    ctx.set_background_color(staticmaps.parse_color("#fafaf9"))

    overlay = TrackOverlay(track, scale=SUPERSAMPLE)
    ctx.add_bounds(bounds_for(track), extra_pixel_bounds=overlay.extra_pixel_bounds())
    ctx.add_object(overlay)
    labels = LabelsOverlay(cache_dir)
    if tile_downloader is not None:
        labels.downloader = tile_downloader
    ctx.add_object(labels)

    render_w, render_h = width * SUPERSAMPLE, map_height * SUPERSAMPLE
    rendered = ctx.render_pillow(render_w, render_h)
    box = _crop_box(ctx, track, render_w, render_h, width / map_height)
    if box is not None:
        rendered = rendered.crop(box)
    rendered = rendered.convert("RGB").resize((width, map_height), Image.LANCZOS)

    canvas = Image.new("RGB", (width, height), SURFACE)
    canvas.paste(rendered, (0, 0))
    _draw_footer(canvas, track, width, map_height)

    buf = io.BytesIO()
    canvas.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
