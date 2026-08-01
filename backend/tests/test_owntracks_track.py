import json
from pathlib import Path

import pendulum
import pytest

from mydiary.owntracks_track import (
    AFTERNOON,
    EVENING,
    MORNING,
    NIGHT,
    TrackParams,
    TrackPoint,
    build_track,
    dedupe,
    despike,
    detect_stays,
    filter_accuracy,
    haversine_m,
    period_for,
    summary_label,
    track_to_geojson,
)

TZ = "America/New_York"


def load_fixture(rootdir: str, name: str):
    items = json.loads(Path(rootdir).joinpath("owntracks_data", name).read_text())
    return [
        TrackPoint(
            tst=pendulum.from_timestamp(x["tst"], tz=TZ),
            lat=x["lat"],
            lon=x["lon"],
            acc=x.get("acc"),
            motion=",".join(x.get("motionactivities") or []) or None,
        )
        for x in sorted(items, key=lambda x: x["tst"])
    ]


@pytest.fixture
def july1(rootdir: str):
    """2026-07-01: a long morning-to-afternoon dwell at home, two outings, and
    a 2h49m gap between them."""
    return load_fixture(rootdir, "owntracks_2026-07-01.json")


@pytest.fixture
def june27(rootdir: str):
    """2026-06-27: a busy day carrying 11 cell-tower fixes accurate only to
    500m-3km."""
    return load_fixture(rootdir, "owntracks_2026-06-27.json")


def test_haversine_known_distance():
    # one degree of latitude is ~111km
    assert haversine_m(32.73, -40, 33.73, -40) == pytest.approx(111195, rel=0.01)


def test_haversine_zero():
    assert haversine_m(33.498, -42.0054, 33.498, -42.0054) == 0


@pytest.mark.parametrize(
    "hour,expected",
    [
        (0, NIGHT),
        (4, NIGHT),
        (5, MORNING),
        (11, MORNING),
        (12, AFTERNOON),
        (16, AFTERNOON),
        (17, EVENING),
        (20, EVENING),
        (21, NIGHT),
        (23, NIGHT),
    ],
)
def test_period_boundaries(hour, expected):
    assert period_for(pendulum.datetime(2026, 7, 1, hour, tz=TZ)) is expected


def test_dedupe_drops_repeated_fix(july1):
    # the recorder stores two records for the 14:11:55 fix, same position
    assert len(dedupe(july1)) == len(july1) - 1


def test_dedupe_keeps_distinct_positions():
    t = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    points = [TrackPoint(t, 33.498, -42.0054), TrackPoint(t, 33.5, -42.0054)]
    assert len(dedupe(points)) == 2


def test_filter_accuracy_drops_cell_tower_fixes(june27):
    kept = filter_accuracy(june27, max_acc=100)
    assert len(kept) < len(june27)
    assert all(p.acc is None or p.acc <= 100 for p in kept)
    # the 500m+ fixes are the ones that make the raw map look scattered
    assert any(p.acc and p.acc > 500 for p in june27)
    assert not any(p.acc and p.acc > 500 for p in kept)


def test_filter_accuracy_keeps_points_without_accuracy():
    t = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    points = [TrackPoint(t, 33.498, -42.0054, acc=None)]
    assert filter_accuracy(points, max_acc=100) == points


def test_despike_drops_isolated_excursion():
    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    points = [
        TrackPoint(base, 33.498, -42.0054),
        TrackPoint(base.add(minutes=1), 44.23, -42.0054),  # 1200km away and back
        TrackPoint(base.add(minutes=2), 33.499, -42.0054),
    ]
    kept = despike(points, max_kmh=TrackParams().max_kmh)
    assert len(kept) == 2
    assert all(p.lat < 41 for p in kept)


def test_despike_keeps_a_flight():
    # a transcontinental flight is fast, but it does not come back -- these are
    # real days in the data and must survive
    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    points = [
        TrackPoint(base.add(hours=i), 33.498 - i * 3.0, -42.0054 - i * 14.0)
        for i in range(4)
    ]
    assert len(despike(points, max_kmh=TrackParams().max_kmh)) == 4


def test_detect_stays_collapses_the_home_cluster(july1):
    stays, _ = detect_stays(dedupe(july1), radius_m=150, min_minutes=20)
    assert len(stays) == 1
    stay = stays[0]
    # 08:05 through 14:27, five pings that would otherwise stack into a blob
    assert stay.num_points == 5
    assert stay.t_start.hour == 8
    assert stay.t_end.hour == 14
    assert stay.duration_minutes == pytest.approx(382, abs=1)
    assert stay.duration_label() == "6h22m"


def test_detect_stays_ignores_brief_pauses():
    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    points = [
        TrackPoint(base.add(minutes=i), 33.498, -42.0054) for i in range(5)
    ]  # only 4 minutes
    stays, _ = detect_stays(points, radius_m=150, min_minutes=20)
    assert stays == []


def test_gap_with_little_movement_becomes_a_stay(july1):
    # 14:27 -> 17:16 covers 434m in 2h49m. the phone reports on significant
    # location change, so that silence is someone sitting still, not a journey
    track = build_track(july1)
    covering = [
        s
        for s in track.stays
        if s.t_start.hour <= 14 and s.t_end.hour >= 17
    ]
    assert len(covering) == 1
    assert not any(link.uncertain for link in track.links)


def test_long_fast_gap_is_dashed_not_a_stay():
    # a flight: a long gap that really did cover ground. the route is unknown,
    # so it is drawn dashed rather than asserted
    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    points = [
        TrackPoint(base, 33.498, -42.0054),
        TrackPoint(base.add(hours=6), 26.782, -82.2279),  # Los Angeles
    ]
    track = build_track(points)
    assert track.stays == []
    assert len(track.links) == 1
    assert track.links[0].uncertain


def test_build_track_does_not_dash_short_hops(july1):
    # a 72-minute gap covering only 151m is a pause, not an unknown route
    track = build_track(july1)
    short = [
        link for link in track.links if link.distance_m < 200 and link.uncertain
    ]
    assert short == []


def test_build_track_summary(july1):
    track = build_track(july1)
    assert track.num_points == 17
    assert track.num_dropped == 1
    assert len(track.stays) == 3
    assert track.distance_m == pytest.approx(3200, abs=200)
    assert summary_label(track) == "3.2 km · 3 stops"


def test_build_track_empty_input():
    track = build_track([])
    assert track.is_empty()
    assert track.bounds() is None
    assert track.num_points == 0


def test_build_track_single_point():
    points = [TrackPoint(pendulum.datetime(2026, 7, 1, 9, tz=TZ), 33.498, -42.0054)]
    track = build_track(points)
    assert track.links == []
    assert track.stays == []
    assert track.bounds() is None  # nothing to draw


def test_bounds_covers_stays_and_links(july1):
    track = build_track(july1)
    min_lat, min_lon, max_lat, max_lon = track.bounds()
    assert min_lat < max_lat and min_lon < max_lon
    assert 33.49 < min_lat < 33.51
    assert -42.0182 < min_lon < -41.9909


def test_content_hash_is_stable_and_param_sensitive(july1):
    params = TrackParams()
    track = build_track(july1, params)
    assert track.content_hash(params) == build_track(july1, params).content_hash(
        params
    )
    other = TrackParams(stay_minutes=5)
    assert track.content_hash(params) != build_track(july1, other).content_hash(other)


def test_stricter_accuracy_drops_more(june27):
    loose = build_track(june27, TrackParams(max_acc=1000))
    strict = build_track(june27, TrackParams(max_acc=50))
    assert strict.num_points < loose.num_points
    assert strict.num_dropped > loose.num_dropped


def test_geojson_shape(july1):
    gj = track_to_geojson(build_track(july1))
    assert gj["type"] == "FeatureCollection"
    kinds = {f["properties"]["kind"] for f in gj["features"]}
    assert kinds == {"link", "stay"}
    assert gj["properties"]["num_stays"] == 3
    for feature in gj["features"]:
        assert feature["properties"]["color"].startswith("#")
        geometry = feature["geometry"]
        assert geometry["type"] in ("LineString", "Point")


def test_geojson_empty_day():
    gj = track_to_geojson(build_track([]))
    assert gj["features"] == []
    assert gj["properties"]["num_stays"] == 0


def test_merge_stays_folds_overlapping_stays_in_one_place():
    from mydiary.owntracks_track import Stay, merge_stays

    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    stays = [
        Stay(33.498, -42.0054, base, base.add(hours=2), 4),
        Stay(33.4985, -42.0056, base.add(hours=2), base.add(hours=5), 2),
    ]
    merged = merge_stays(stays, radius_m=150)
    assert len(merged) == 1
    assert merged[0].t_start == base
    assert merged[0].t_end == base.add(hours=5)
    assert merged[0].num_points == 6


def test_merge_stays_keeps_distinct_places_apart():
    from mydiary.owntracks_track import Stay, merge_stays

    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    stays = [
        Stay(33.498, -42.0054, base, base.add(hours=2), 4),
        Stay(33.52, -42.0054, base.add(hours=2), base.add(hours=5), 2),  # 2.4km away
    ]
    assert len(merge_stays(stays, radius_m=150)) == 2


def test_gap_stay_anchors_at_the_earlier_fix():
    from mydiary.owntracks_track import detect_gap_stays

    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    points = [
        TrackPoint(base, 33.498, -42.0054),
        TrackPoint(base.add(hours=2), 33.499, -42.0064),
    ]
    stays = detect_gap_stays(points, [], min_minutes=20, max_kmh=1.0)
    assert len(stays) == 1
    # the time was spent where the gap started, not where it ended
    assert stays[0].lat == 33.498
    assert stays[0].t_start == base


def test_gap_stay_not_inferred_when_the_gap_covers_ground():
    from mydiary.owntracks_track import detect_gap_stays

    base = pendulum.datetime(2026, 7, 1, 9, tz=TZ)
    points = [
        TrackPoint(base, 33.498, -42.0054),
        TrackPoint(base.add(hours=1), 33.58, -42.0054),  # 9km in an hour
    ]
    assert detect_gap_stays(points, [], min_minutes=20, max_kmh=1.0) == []
