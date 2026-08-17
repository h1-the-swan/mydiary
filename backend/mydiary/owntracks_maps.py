# -*- coding: utf-8 -*-

DESCRIPTION = """Put a day's rendered location map into its Joplin note.

The map is a generated image, not a photo, so it deliberately stays out of
MyDiaryImage and the photo grid: it lives in its own Location section and its
own bookkeeping table. That table exists so a re-render of an unchanged day
reuses its Joplin resource rather than orphaning one."""

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Sequence, Tuple

import pendulum
from sqlmodel import Session, select

from .db import engine
from .joplin_connector import MyDiaryJoplin
from .map_render import RenderParams, render_day_map
from .markdown_edits import MarkdownDoc
from .models import OwnTracksDayMap
from .mydiary_day import MyDiaryDay
from .owntracks_connector import MyDiaryOwnTracks
from .owntracks_track import AREA_SPLIT_M, DayTrack, TrackParams, split_into_areas

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

SECTION_TITLE = "Location"
# the Location section goes right after the photos
SECTION_AFTER = "Images"


@dataclass(frozen=True)
class Panel:
    """One map that ends up in the note.

    Panel 0 is always the whole-day overview -- on most days the only map there
    is. A day split across distinct areas keeps that overview (on a flight day
    "I went from here to there" is real information) and adds a panel per area,
    framed tightly enough to actually read.
    """

    kind: str  # "overview" | "area"
    label: str  # "" for the overview, "08:12-11:40" for an area
    track: DayTrack  # what gets drawn
    frame: Optional[DayTrack]  # what it is framed on; None means the whole track
    content_hash: str


def day_track(
    dt: datetime, session: Session, params: Optional[TrackParams] = None
) -> DayTrack:
    """The day's processed track, or LookupError if there is nothing to draw."""
    from .owntracks_track import build_track, points_from_locations

    params = params or TrackParams()
    dt = pendulum.instance(dt)
    locations = MyDiaryOwnTracks().get_locations_for_day(dt, session=session)
    if not locations:
        raise LookupError(f"no location data for {dt.to_date_string()}")
    track = build_track(
        points_from_locations(locations, timezone=dt.timezone_name), params
    )
    if track.is_empty():
        raise LookupError(
            f"no usable location data for {dt.to_date_string()} "
            f"({len(locations)} fixes, all filtered out)"
        )
    return track


def _content_hash(
    track: DayTrack, params: TrackParams, render: RenderParams, suffix: str = ""
) -> str:
    """Digest of what a panel will look like, for resource reuse.

    Covers the render parameters as well as the track, so changing the size or
    the encoding invalidates a stored map the same way new location data does.
    Composed here rather than in owntracks_track, which is pure track maths and
    has no business knowing about image encoding.
    """
    key = f"{track.content_hash(params)}|{render.cache_key()}"
    if suffix:
        key = f"{key}|{suffix}"
    return hashlib.sha256(key.encode()).hexdigest()


def panels_for_track(
    track: DayTrack,
    params: Optional[TrackParams] = None,
    render: Optional[RenderParams] = None,
    area_threshold_m: float = AREA_SPLIT_M,
) -> List[Panel]:
    """The maps a track needs: the overview, plus one per distinct area.

    A one-area day gets one panel, and that panel's track *is* the whole day --
    so it hashes to exactly what a day map hashed to before panels existed, and
    no already-synced day is invalidated by this. The same holds for the
    overview panel of a multi-area day, whose resource is therefore reused.
    """
    params = params or TrackParams()
    render = render or RenderParams()
    panels = [
        Panel("overview", "", track, None, _content_hash(track, params, render))
    ]
    # empty on a day one frame already fits, which is most of them
    panels.extend(
        Panel(
            "area",
            area.label(),
            area.track,
            area.frame,
            _content_hash(area.track, params, render, _area_key(i, area)),
        )
        for i, area in enumerate(split_into_areas(track, area_threshold_m))
    )
    return panels


def _area_key(i: int, area) -> str:
    """What distinguishes this panel from the same content drawn differently.

    The index keeps two identical-looking areas apart, and the frame is in here
    because it decides the zoom: change how panels are framed and every stored
    area panel has to know it is stale, or a re-sync reports no update and
    leaves the old picture in the note.
    """
    b = area.frame.bounds()
    frame = "none" if b is None else ",".join(f"{x:.6f}" for x in b)
    return f"area{i}|frame={frame}"


def panels_for_day(
    dt: datetime,
    session: Session,
    params: Optional[TrackParams] = None,
    render: Optional[RenderParams] = None,
    area_threshold_m: float = AREA_SPLIT_M,
) -> Tuple[DayTrack, List[Panel]]:
    """panels_for_track, for a day that has to be loaded from the database."""
    params = params or TrackParams()
    track = day_track(dt, session, params)
    return track, panels_for_track(track, params, render, area_threshold_m)


def render_for_day(
    dt: datetime,
    session: Session,
    params: Optional[TrackParams] = None,
    render: Optional[RenderParams] = None,
    panel: int = 0,
) -> Tuple[bytes, DayTrack, str]:
    """Render one of the day's maps. Returns (image bytes, track, content_hash).

    Panel 0 is the whole-day overview; higher indices select an area panel on a
    day that has more than one area.
    """
    params = params or TrackParams()
    render = render or RenderParams()
    _, panels = panels_for_day(dt, session, params, render)
    if not 0 <= panel < len(panels):
        raise LookupError(
            f"{pendulum.instance(dt).to_date_string()} has {len(panels)} map"
            f"{'' if len(panels) == 1 else 's'}, so there is no panel {panel}"
        )
    chosen = panels[panel]
    data = render_day_map(chosen.track, params, render, frame=chosen.frame)
    return data, chosen.track, chosen.content_hash


def sync_day_map_to_note(
    dt: datetime,
    session: Optional[Session] = None,
    mydiary_joplin: Optional[MyDiaryJoplin] = None,
    params: Optional[TrackParams] = None,
    force: bool = False,
    render: Optional[RenderParams] = None,
) -> Tuple[str, int]:
    """Render the day's map(s), upload to Joplin, and write the Location section.

    Returns (result, number of maps written). Re-running for an unchanged day is
    a no-op: the content hash covers both the processed track and the render
    parameters.
    """
    close_session = session is None
    if session is None:
        session = Session(engine)
    close_joplin = mydiary_joplin is None
    if mydiary_joplin is None:
        mydiary_joplin = MyDiaryJoplin(init_config=False)
        mydiary_joplin.__enter__()
    try:
        return _sync_day_map_to_note(dt, session, mydiary_joplin, params, force, render)
    finally:
        if close_joplin:
            mydiary_joplin.__exit__(None, None, None)
        if close_session:
            session.close()


def _sync_day_map_to_note(
    dt: datetime,
    session: Session,
    mydiary_joplin: MyDiaryJoplin,
    params: Optional[TrackParams],
    force: bool,
    render: Optional[RenderParams] = None,
) -> Tuple[str, int]:
    dt = pendulum.instance(dt)
    diary_date = dt.date()
    params = params or TrackParams()
    render = render or RenderParams()
    _, panels = panels_for_day(dt, session, params, render)

    existing = list(
        session.exec(
            select(OwnTracksDayMap)
            .where(OwnTracksDayMap.diary_date == diary_date)
            .order_by(OwnTracksDayMap.panel)
        )
    )
    if (
        not force
        and [row.content_hash for row in existing] == [p.content_hash for p in panels]
        and all(
            mydiary_joplin.resource_exists(row.joplin_resource_id) for row in existing
        )
    ):
        logger.info(f"owntracks map for {diary_date} is already up to date")
        return "no update", len(panels)

    note_id = mydiary_joplin.get_note_id_by_date(dt)
    if note_id is None or note_id == "does_not_exist":
        raise LookupError(f"no Joplin note for {diary_date}")

    # an unchanged panel keeps its resource, so a day that gains areas re-uploads
    # only the new panels and leaves its overview alone
    reusable = (
        {}
        if force
        else {
            row.content_hash: row.joplin_resource_id
            for row in existing
            if mydiary_joplin.resource_exists(row.joplin_resource_id)
        }
    )
    old_resource_ids = [row.joplin_resource_id for row in existing]

    resource_ids: List[str] = []
    created: List[str] = []
    try:
        for i, panel in enumerate(panels):
            resource_id = reusable.get(panel.content_hash)
            if resource_id is None:
                data = render_day_map(
                    panel.track, params, render, frame=panel.frame
                )
                # Joplin takes the resource's mime from this extension, so it is
                # the only thing the note needs to render a non-PNG map
                title = f"map-{diary_date}" if i == 0 else f"map-{diary_date}-{i}"
                r = mydiary_joplin.create_resource(
                    data=data, title=title, ext=render.ext
                )
                r.raise_for_status()
                resource_id = r.json()["id"]
                created.append(resource_id)
            resource_ids.append(resource_id)

        note = mydiary_joplin.get_note(note_id)
        md_note = MarkdownDoc(note.body, parent=note)
        # an old note predating this feature has no Location section at all, and
        # update_joplin_note will never add one
        section = md_note.ensure_section(SECTION_TITLE, after_title=SECTION_AFTER)
        section.set_content(section_content(resource_ids, panels))
        response = mydiary_joplin.update_note_body(note_id, md_note.txt)
        response.raise_for_status()

        for i, (panel, resource_id) in enumerate(zip(panels, resource_ids)):
            session.merge(
                OwnTracksDayMap(
                    diary_date=diary_date,
                    panel=i,
                    joplin_resource_id=resource_id,
                    content_hash=panel.content_hash,
                    num_points=panel.track.num_points,
                    num_stays=len(panel.track.stays),
                    distance_m=int(panel.track.distance_m),
                    created_at=pendulum.now(tz="UTC"),
                )
            )
        # a day that lost an area leaves rows behind that nothing points at
        for row in existing:
            if row.panel >= len(panels):
                session.delete(row)
        session.commit()
    except Exception:
        session.rollback()
        for resource_id in created:
            try:
                mydiary_joplin.delete_resource(resource_id, force=True)
            except Exception:
                logger.warning(f"failed to clean up joplin resource {resource_id}")
        raise

    # the note now points at the new resources, so superseded ones are safe to drop
    for resource_id in old_resource_ids:
        if resource_id in resource_ids:
            continue
        try:
            mydiary_joplin.delete_resource(resource_id, force=True)
        except Exception:
            logger.warning(f"failed to delete superseded resource {resource_id}")
    return "updated", len(panels)


def section_content(
    resource_ids: Sequence[Optional[str]], panels: Sequence[Panel]
) -> str:
    """The Location section body: the map(s), then a searchable itinerary.

    The itinerary is the part that keeps working -- Joplin can search text, but
    it cannot search an image.

    One panel is the common case and emits exactly what it always has. A day
    split across areas leads with the whole-day overview, then gives each area
    its own heading, map and itinerary -- the day-level table would only repeat
    what the per-area ones say, since every stay belongs to exactly one area.
    """
    if len(panels) == 1:
        return _panel_content(resource_ids[0], panels[0].track)

    parts = [_panel_content(resource_ids[0], panels[0].track, itinerary=False)]
    for resource_id, panel in zip(resource_ids[1:], panels[1:]):
        # level 3, so MarkdownDoc (which splits on "## ") keeps this one section
        parts.append(f"### {panel.label}\n\n{_panel_content(resource_id, panel.track)}")
    return "\n\n".join(parts)


def _panel_content(
    resource_id: Optional[str], track: DayTrack, itinerary: bool = True
) -> str:
    from .owntracks_track import summary_label
    from .models import make_markdown_table_header

    lines = []
    if resource_id:
        lines.extend([f"![](:/{resource_id})", ""])
    lines.append(summary_label(track))
    if itinerary and track.stays:
        lines.append("")
        lines.append(make_markdown_table_header(["Arrive", "Depart", "Duration", "Where"]))
        for stay in track.stays:
            lines.append(
                f"{stay.t_start:%H:%M} | {stay.t_end:%H:%M} | "
                f"{stay.duration_label()} | {stay.lat:.5f}, {stay.lon:.5f}"
            )
    return "\n".join(lines)
