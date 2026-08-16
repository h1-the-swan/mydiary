# -*- coding: utf-8 -*-

DESCRIPTION = """Put a day's rendered location map into its Joplin note.

The map is a generated image, not a photo, so it deliberately stays out of
MyDiaryImage and the photo grid: it lives in its own Location section and its
own bookkeeping table. That table exists so a re-render of an unchanged day
reuses its Joplin resource rather than orphaning one."""

import hashlib
from datetime import datetime
from typing import Optional, Tuple

import pendulum
from sqlmodel import Session, select

from .db import engine
from .joplin_connector import MyDiaryJoplin
from .map_render import RenderParams, render_day_map
from .markdown_edits import MarkdownDoc
from .models import OwnTracksDayMap
from .mydiary_day import MyDiaryDay
from .owntracks_connector import MyDiaryOwnTracks
from .owntracks_track import DayTrack, TrackParams

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

SECTION_TITLE = "Location"
# the Location section goes right after the photos
SECTION_AFTER = "Images"


def render_for_day(
    dt: datetime,
    session: Session,
    params: Optional[TrackParams] = None,
    render: Optional[RenderParams] = None,
) -> Tuple[bytes, DayTrack, str]:
    """Render the map for a day. Returns (image bytes, track, content_hash).

    The hash covers the render parameters as well as the track, so changing the
    size or the encoding invalidates a stored map the same way new location
    data does. It is composed here rather than in owntracks_track, which is
    pure track maths and has no business knowing about image encoding.
    """
    params = params or TrackParams()
    render = render or RenderParams()
    mydiary_owntracks = MyDiaryOwnTracks()
    locations = mydiary_owntracks.get_locations_for_day(dt, session=session)
    if not locations:
        raise LookupError(f"no location data for {pendulum.instance(dt).to_date_string()}")
    from .owntracks_track import build_track, points_from_locations

    dt = pendulum.instance(dt)
    track = build_track(
        points_from_locations(locations, timezone=dt.timezone_name), params
    )
    if track.is_empty():
        raise LookupError(
            f"no usable location data for {dt.to_date_string()} "
            f"({len(locations)} fixes, all filtered out)"
        )
    data = render_day_map(track, params, render)
    content_hash = hashlib.sha256(
        f"{track.content_hash(params)}|{render.cache_key()}".encode()
    ).hexdigest()
    return data, track, content_hash


def sync_day_map_to_note(
    dt: datetime,
    session: Optional[Session] = None,
    mydiary_joplin: Optional[MyDiaryJoplin] = None,
    params: Optional[TrackParams] = None,
    force: bool = False,
    render: Optional[RenderParams] = None,
) -> str:
    """Render the day's map, upload it to Joplin, and write the Location section.

    Re-running for an unchanged day is a no-op: the content hash covers both the
    processed track and the render parameters.
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
) -> str:
    dt = pendulum.instance(dt)
    diary_date = dt.date()
    render = render or RenderParams()
    data, track, content_hash = render_for_day(dt, session, params, render)

    existing = session.get(OwnTracksDayMap, diary_date)
    if (
        existing is not None
        and existing.content_hash == content_hash
        and not force
        and mydiary_joplin.resource_exists(existing.joplin_resource_id)
    ):
        logger.info(f"owntracks map for {diary_date} is already up to date")
        return "no update"

    note_id = mydiary_joplin.get_note_id_by_date(dt)
    if note_id is None or note_id == "does_not_exist":
        raise LookupError(f"no Joplin note for {diary_date}")

    # Joplin takes the resource's mime from this extension, so it is the only
    # thing the note needs in order to render a non-PNG map
    r = mydiary_joplin.create_resource(
        data=data, title=f"map-{diary_date}", ext=render.ext
    )
    r.raise_for_status()
    resource_id = r.json()["id"]

    old_resource_id = existing.joplin_resource_id if existing is not None else None
    try:
        note = mydiary_joplin.get_note(note_id)
        md_note = MarkdownDoc(note.body, parent=note)
        # an old note predating this feature has no Location section at all, and
        # update_joplin_note will never add one
        section = md_note.ensure_section(SECTION_TITLE, after_title=SECTION_AFTER)
        section.set_content(section_content(resource_id, track))
        response = mydiary_joplin.update_note_body(note_id, md_note.txt)
        response.raise_for_status()

        session.merge(
            OwnTracksDayMap(
                diary_date=diary_date,
                joplin_resource_id=resource_id,
                content_hash=content_hash,
                num_points=track.num_points,
                num_stays=len(track.stays),
                distance_m=int(track.distance_m),
                created_at=pendulum.now(tz="UTC"),
            )
        )
        session.commit()
    except Exception:
        session.rollback()
        try:
            mydiary_joplin.delete_resource(resource_id, force=True)
        except Exception:
            logger.warning(f"failed to clean up joplin resource {resource_id}")
        raise

    # the note now points at the new resource, so the old one is safe to drop
    if old_resource_id and old_resource_id != resource_id:
        try:
            mydiary_joplin.delete_resource(old_resource_id, force=True)
        except Exception:
            logger.warning(f"failed to delete superseded resource {old_resource_id}")
    return "updated"


def section_content(resource_id: Optional[str], track: DayTrack) -> str:
    """The Location section body: the map, then a searchable itinerary.

    The itinerary is the part that keeps working -- Joplin can search text, but
    it cannot search an image.
    """
    from .owntracks_track import summary_label
    from .models import make_markdown_table_header

    lines = []
    if resource_id:
        lines.extend([f"![](:/{resource_id})", ""])
    lines.append(summary_label(track))
    if track.stays:
        lines.append("")
        lines.append(make_markdown_table_header(["Arrive", "Depart", "Duration", "Where"]))
        for stay in track.stays:
            lines.append(
                f"{stay.t_start:%H:%M} | {stay.t_end:%H:%M} | "
                f"{stay.duration_label()} | {stay.lat:.5f}, {stay.lon:.5f}"
            )
    return "\n".join(lines)
