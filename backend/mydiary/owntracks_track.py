# -*- coding: utf-8 -*-

DESCRIPTION = """Turn raw OwnTracks fixes into something worth drawing.

The phone reports in significant-location-change mode, so a day is 15-80 fixes,
not a continuous trace. Drawn raw that produces a tangle: multi-hour gaps become
straight lines through buildings, cell-tower fixes accurate to 3km jump the
position across a neighbourhood, and a dozen near-identical pings at home pile
into one blob.

This module is pure functions over point lists -- no network, no database, no
drawing -- so the thresholds can be tuned and tested on their own."""

import hashlib
import math
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

import pendulum

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


EARTH_RADIUS_M = 6371000.0


@dataclass(frozen=True)
class TrackParams:
    """Every threshold in one place, so the API can expose them for tuning."""

    # drop fixes worse than this (metres). ~16% of real fixes are worse than
    # 100m, and the tail runs to 3km -- those are the position jumps.
    max_acc: int = 100
    # drop a fix implying travel faster than this (km/h) that immediately
    # reverses. set above airliner cruise on purpose: flights are in this data
    # (a 3900km day is a real transcontinental, not an artifact), and only a
    # physically impossible there-and-back should ever be discarded.
    max_kmh: float = 1200.0
    # fixes staying within this radius (metres) of their running centroid...
    stay_radius_m: float = 150.0
    # ...for at least this long (minutes) are one stay
    stay_minutes: float = 20.0
    # the phone only reports when it moves, so it goes quiet exactly when you
    # stop. a long gap that ends up near where it started is a dwell, not a
    # journey -- infer a stay when the implied speed across it is below this.
    dwell_max_kmh: float = 1.0
    # a link across a bigger time gap than this (minutes) covering more than
    # gap_metres is drawn dashed: we genuinely do not know the route. the
    # distance floor keeps short hops out of it -- dashing a 150m link implies
    # an unknown route over a distance where there is barely a route to know.
    gap_minutes: float = 45.0
    gap_metres: float = 250.0

    def cache_key(self) -> str:
        return "|".join(
            f"{k}={v}" for k, v in sorted(self.__dict__.items())
        )


@dataclass(frozen=True)
class Period:
    name: str
    color: str

    def __str__(self) -> str:
        return self.name


NIGHT = Period("Night", "#4a3aa7")
MORNING = Period("Morning", "#1baf7a")
AFTERNOON = Period("Afternoon", "#eb6834")
EVENING = Period("Evening", "#2a78d6")

# (start_hour, end_hour, period), local time. validated as a 4-slot categorical
# palette under all-pairs CVD comparison -- see docs.
PERIOD_BINS: Tuple[Tuple[int, int, Period], ...] = (
    (5, 12, MORNING),
    (12, 17, AFTERNOON),
    (17, 21, EVENING),
)
PERIODS: Tuple[Period, ...] = (MORNING, AFTERNOON, EVENING, NIGHT)
PERIOD_LABELS: Tuple[Tuple[Period, str], ...] = (
    (MORNING, "05-12"),
    (AFTERNOON, "12-17"),
    (EVENING, "17-21"),
    (NIGHT, "21-05"),
)


def period_for(dt: datetime) -> Period:
    """Which named part of the (local) day a timestamp falls in."""
    hour = dt.hour
    for start, end, period in PERIOD_BINS:
        if start <= hour < end:
            return period
    return NIGHT


@dataclass(frozen=True)
class TrackPoint:
    tst: datetime  # timezone-aware, in the day's local timezone
    lat: float
    lon: float
    acc: Optional[int] = None
    motion: Optional[str] = None


@dataclass(frozen=True)
class Stay:
    """Somewhere the day paused for a while."""

    lat: float
    lon: float
    t_start: datetime
    t_end: datetime
    num_points: int

    @property
    def duration_minutes(self) -> float:
        return (self.t_end - self.t_start).total_seconds() / 60.0

    @property
    def midpoint(self) -> datetime:
        return self.t_start + (self.t_end - self.t_start) / 2

    @property
    def period(self) -> Period:
        return period_for(self.midpoint)

    def duration_label(self) -> str:
        minutes = int(round(self.duration_minutes))
        hours, minutes = divmod(minutes, 60)
        if hours and minutes:
            return f"{hours}h{minutes:02d}m"
        if hours:
            return f"{hours}h"
        return f"{minutes}m"


@dataclass(frozen=True)
class Link:
    """A drawn connection between two consecutive nodes of the day."""

    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    t_start: datetime
    t_end: datetime
    distance_m: float
    uncertain: bool

    @property
    def period(self) -> Period:
        return period_for(self.t_start + (self.t_end - self.t_start) / 2)


@dataclass(frozen=True)
class DayTrack:
    stays: List[Stay] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    num_points: int = 0
    num_dropped: int = 0
    distance_m: float = 0.0

    def is_empty(self) -> bool:
        return not self.stays and not self.links

    def bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """(min_lat, min_lon, max_lat, max_lon) over everything drawn."""
        lats: List[float] = [s.lat for s in self.stays]
        lons: List[float] = [s.lon for s in self.stays]
        for link in self.links:
            lats.extend((link.start_lat, link.end_lat))
            lons.extend((link.start_lon, link.end_lon))
        if not lats:
            return None
        return min(lats), min(lons), max(lats), max(lons)

    def content_hash(self, params: TrackParams) -> str:
        """Stable digest of what will be drawn, for resource reuse."""
        h = hashlib.sha256()
        h.update(params.cache_key().encode())
        for s in self.stays:
            h.update(f"S{s.lat:.6f},{s.lon:.6f},{s.t_start},{s.t_end}".encode())
        for link in self.links:
            h.update(
                f"L{link.start_lat:.6f},{link.start_lon:.6f},"
                f"{link.end_lat:.6f},{link.end_lon:.6f},"
                f"{link.t_start},{link.uncertain}".encode()
            )
        return h.hexdigest()


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def points_from_locations(
    locations: Iterable, timezone: str = "UTC"
) -> List[TrackPoint]:
    """Convert OwnTracksLocation rows (UTC, possibly naive) to local TrackPoints."""
    points = []
    for loc in locations:
        tst = pendulum.instance(loc.tst, tz="UTC").in_timezone(timezone)
        points.append(
            TrackPoint(
                tst=tst, lat=loc.lat, lon=loc.lon, acc=loc.acc, motion=loc.motion
            )
        )
    points.sort(key=lambda p: p.tst)
    return points


def dedupe(points: Sequence[TrackPoint]) -> List[TrackPoint]:
    """Drop repeats of the same instant and position.

    The recorder legitimately stores two records for one fix when it arrives by
    more than one route -- same tst, same position, different trigger.
    """
    seen = set()
    out = []
    for p in points:
        key = (p.tst, round(p.lat, 6), round(p.lon, 6))
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def filter_accuracy(
    points: Sequence[TrackPoint], max_acc: int
) -> List[TrackPoint]:
    """Drop fixes too imprecise to place on a street-scale map.

    A fix with acc=3000 is a cell-tower guess; drawing it asserts a trip across
    the neighbourhood that never happened.
    """
    return [p for p in points if p.acc is None or p.acc <= max_acc]


def despike(points: Sequence[TrackPoint], max_kmh: float) -> List[TrackPoint]:
    """Drop isolated fixes implying an impossible out-and-back.

    Only excursions are removed: a point is dropped when reaching it *and*
    leaving it both exceed max_kmh but going straight from its predecessor to
    its successor does not. Genuine fast travel (a train) survives.
    """
    if len(points) < 3:
        return list(points)
    out = [points[0]]
    for i in range(1, len(points) - 1):
        cur, nxt = points[i], points[i + 1]
        prev = out[-1]  # compare against the last point we kept, not the last seen
        if (
            _implied_kmh(prev, cur) > max_kmh
            and _implied_kmh(cur, nxt) > max_kmh
            and _implied_kmh(prev, nxt) <= max_kmh
        ):
            logger.debug(f"despike: dropping outlier fix at {cur.tst}")
            continue
        out.append(cur)
    out.append(points[-1])
    return out


def _implied_kmh(a: TrackPoint, b: TrackPoint) -> float:
    seconds = abs((b.tst - a.tst).total_seconds())
    if seconds == 0:
        return 0.0
    return haversine_m(a.lat, a.lon, b.lat, b.lon) / seconds * 3.6


def detect_stays(
    points: Sequence[TrackPoint], radius_m: float, min_minutes: float
) -> Tuple[List[Stay], List[Tuple[int, int]]]:
    """Group consecutive fixes that stayed put.

    The classic stay-point formulation (Li et al. 2008): walk forward
    accumulating fixes while they remain within radius_m of the group's running
    centroid; emit a Stay if the group spans at least min_minutes.

    Returns the stays and the (start, end) index ranges they consumed.
    """
    stays: List[Stay] = []
    ranges: List[Tuple[int, int]] = []
    i = 0
    n = len(points)
    while i < n:
        lat_sum, lon_sum = points[i].lat, points[i].lon
        j = i + 1
        while j < n:
            c_lat = lat_sum / (j - i)
            c_lon = lon_sum / (j - i)
            if haversine_m(c_lat, c_lon, points[j].lat, points[j].lon) > radius_m:
                break
            lat_sum += points[j].lat
            lon_sum += points[j].lon
            j += 1
        span = (points[j - 1].tst - points[i].tst).total_seconds() / 60.0
        if j - i >= 2 and span >= min_minutes:
            count = j - i
            stays.append(
                Stay(
                    lat=lat_sum / count,
                    lon=lon_sum / count,
                    t_start=points[i].tst,
                    t_end=points[j - 1].tst,
                    num_points=count,
                )
            )
            ranges.append((i, j))
            i = j
        else:
            i += 1
    return stays, ranges


def detect_gap_stays(
    points: Sequence[TrackPoint],
    consumed: Sequence[Tuple[int, int]],
    min_minutes: float,
    max_kmh: float,
) -> List[Stay]:
    """Infer stays from the silence between fixes.

    detect_stays can only group fixes that exist, but this phone reports on
    significant location change: standing still produces no fixes at all. A
    two-hour gap that ends 300m from where it began is someone sitting at home,
    not someone travelling. Anchored at the earlier fix -- that is where the
    time was actually spent.
    """
    in_stay = set()
    for start, end in consumed:
        in_stay.update(range(start, end))
    stays: List[Stay] = []
    for i in range(len(points) - 1):
        if i in in_stay and (i + 1) in in_stay:
            continue  # already inside a detected stay
        a, b = points[i], points[i + 1]
        minutes = (b.tst - a.tst).total_seconds() / 60.0
        if minutes < min_minutes:
            continue
        if _implied_kmh(a, b) > max_kmh:
            continue
        stays.append(
            Stay(lat=a.lat, lon=a.lon, t_start=a.tst, t_end=b.tst, num_points=2)
        )
    return stays


def merge_stays(stays: Sequence[Stay], radius_m: float) -> List[Stay]:
    """Fold together stays that overlap in time and are in the same place."""
    ordered = sorted(stays, key=lambda s: s.t_start)
    merged: List[Stay] = []
    for stay in ordered:
        if merged:
            last = merged[-1]
            close = haversine_m(last.lat, last.lon, stay.lat, stay.lon) <= radius_m * 2
            overlapping = stay.t_start <= last.t_end
            if close and overlapping:
                total = last.num_points + stay.num_points
                merged[-1] = Stay(
                    lat=(last.lat * last.num_points + stay.lat * stay.num_points) / total,
                    lon=(last.lon * last.num_points + stay.lon * stay.num_points) / total,
                    t_start=last.t_start,
                    t_end=max(last.t_end, stay.t_end),
                    num_points=total,
                )
                continue
        merged.append(stay)
    return merged


@dataclass(frozen=True)
class _Node:
    lat: float
    lon: float
    t_start: datetime
    t_end: datetime


def build_track(
    points: Sequence[TrackPoint], params: Optional[TrackParams] = None
) -> DayTrack:
    """Full pipeline: raw local points in, drawable DayTrack out."""
    params = params or TrackParams()
    raw_count = len(points)
    cleaned = despike(
        filter_accuracy(dedupe(points), params.max_acc), params.max_kmh
    )
    if not cleaned:
        return DayTrack(num_points=0, num_dropped=raw_count)

    stays, ranges = detect_stays(
        cleaned, params.stay_radius_m, params.stay_minutes
    )
    gap_stays = detect_gap_stays(
        cleaned, ranges, params.stay_minutes, params.dwell_max_kmh
    )

    # a fix is consumed by the stay it belongs to. a gap-stay consumes only the
    # fix it is anchored at -- the one that ends the gap is where the next leg
    # departs from, so it stays a node of its own.
    in_stay = set()
    for start, end in ranges:
        in_stay.update(range(start, end))
    anchors = {s.t_start for s in gap_stays}
    for i, p in enumerate(cleaned):
        if p.tst in anchors:
            in_stay.add(i)

    stays = merge_stays(stays + gap_stays, params.stay_radius_m)

    # one node per stay, one per fix that is not inside a stay, in time order
    nodes: List[_Node] = [
        _Node(p.lat, p.lon, p.tst, p.tst)
        for i, p in enumerate(cleaned)
        if i not in in_stay
    ]
    nodes.extend(_Node(s.lat, s.lon, s.t_start, s.t_end) for s in stays)
    nodes.sort(key=lambda n: n.t_start)

    links: List[Link] = []
    total_m = 0.0
    for a, b in zip(nodes, nodes[1:]):
        distance = haversine_m(a.lat, a.lon, b.lat, b.lon)
        gap_minutes = (b.t_start - a.t_end).total_seconds() / 60.0
        uncertain = (
            gap_minutes > params.gap_minutes and distance > params.gap_metres
        )
        links.append(
            Link(
                start_lat=a.lat,
                start_lon=a.lon,
                end_lat=b.lat,
                end_lon=b.lon,
                t_start=a.t_end,
                t_end=b.t_start,
                distance_m=distance,
                uncertain=uncertain,
            )
        )
        total_m += distance

    return DayTrack(
        stays=stays,
        links=links,
        num_points=len(cleaned),
        num_dropped=raw_count - len(cleaned),
        distance_m=total_m,
    )


def track_to_geojson(track: DayTrack) -> dict:
    """FeatureCollection for the frontend map -- same pipeline as the PNG."""
    features = []
    for link in track.links:
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [link.start_lon, link.start_lat],
                        [link.end_lon, link.end_lat],
                    ],
                },
                "properties": {
                    "kind": "link",
                    "uncertain": link.uncertain,
                    "period": link.period.name,
                    "color": link.period.color,
                    "t_start": link.t_start.isoformat(),
                    "t_end": link.t_end.isoformat(),
                    "distance_m": round(link.distance_m),
                },
            }
        )
    for stay in track.stays:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [stay.lon, stay.lat]},
                "properties": {
                    "kind": "stay",
                    "period": stay.period.name,
                    "color": stay.period.color,
                    "t_start": stay.t_start.isoformat(),
                    "t_end": stay.t_end.isoformat(),
                    "duration_minutes": round(stay.duration_minutes),
                    "duration_label": stay.duration_label(),
                    "num_points": stay.num_points,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "num_points": track.num_points,
            "num_dropped": track.num_dropped,
            "num_stays": len(track.stays),
            "distance_m": round(track.distance_m),
        },
    }


def summary_label(track: DayTrack) -> str:
    """e.g. '3.3 km - 4 stops'"""
    km = track.distance_m / 1000.0
    distance = f"{km:.1f} km" if km >= 0.1 else f"{round(track.distance_m)} m"
    stops = len(track.stays)
    return f"{distance} · {stops} stop{'' if stops == 1 else 's'}"
