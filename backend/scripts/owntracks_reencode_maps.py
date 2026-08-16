# -*- coding: utf-8 -*-

DESCRIPTION = """Re-encode the OwnTracks maps already embedded in Joplin notes.

The maps used to be saved as PNG, which costs roughly 5x the bytes of the JPEG
they are saved as now for no visible difference. Every day already in
OwnTracksDayMap is re-rendered and its Joplin resource replaced.

Resumable and safe to re-run: OwnTracksDayMap.content_hash now covers the
render parameters, so an un-migrated day hashes differently and gets the work,
while a migrated day hashes equal and is skipped. Run it inside the backend
container -- JOPLIN_BASE_URL points at host.docker.internal, which does not
resolve from the host."""

import sys, os
from datetime import datetime
from timeit import default_timer as timer

import pendulum
from sqlmodel import Session, select

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from mydiary.core import get_last_timezone
from mydiary.db import engine
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.models import OwnTracksDayMap
from mydiary.owntracks_maps import render_for_day, sync_day_map_to_note


def format_bytes(num: int) -> str:
    return f"{num / 1024:,.0f} KB"


def start_of_day(diary_date, session: Session) -> pendulum.DateTime:
    """Start of the day in the day's own timezone, as the API routes do it.

    get_last_timezone raises when TimeZoneChange is empty (todo item 4.3); a
    backfill must not die on that, so it falls back the same way the routes do.
    """
    dt_str = diary_date.isoformat()
    try:
        tz = get_last_timezone(dt_str, session=session)
    except (AttributeError, TypeError):
        logger.warning("could not infer timezone; falling back to local")
        tz = "local"
    return pendulum.parse(dt_str, tz=tz)


def main(args):
    with Session(engine) as session, MyDiaryJoplin(init_config=False) as mydiary_joplin:
        stmt = select(OwnTracksDayMap).order_by(OwnTracksDayMap.diary_date)
        if args.start:
            stmt = stmt.where(
                OwnTracksDayMap.diary_date >= pendulum.parse(args.start).date()
            )
        if args.end:
            stmt = stmt.where(
                OwnTracksDayMap.diary_date <= pendulum.parse(args.end).date()
            )
        if args.limit:
            stmt = stmt.limit(args.limit)
        rows = session.exec(stmt).all()
        logger.info(f"{len(rows)} day map(s) to consider")

        total_before = 0
        total_after = 0
        num_updated = 0
        num_skipped = 0
        num_failed = 0

        for row in rows:
            diary_date = row.diary_date
            before = mydiary_joplin.get_resource_size(row.joplin_resource_id)
            try:
                dt = start_of_day(diary_date, session)
                if args.dry_run:
                    data, _, content_hash = render_for_day(dt, session)
                    if content_hash == row.content_hash:
                        logger.info(f"{diary_date}: already up to date")
                        num_skipped += 1
                        continue
                    after = len(data)
                else:
                    result = sync_day_map_to_note(
                        dt, session=session, mydiary_joplin=mydiary_joplin
                    )
                    if result == "no update":
                        logger.info(f"{diary_date}: already up to date")
                        num_skipped += 1
                        continue
                    session.expire(row)
                    after = mydiary_joplin.get_resource_size(row.joplin_resource_id)
            except LookupError as e:
                # no Joplin note for the day, or no usable location data left
                logger.warning(f"{diary_date}: skipped -- {e}")
                num_failed += 1
                continue

            num_updated += 1
            if before is None or after is None:
                logger.info(f"{diary_date}: updated (size unavailable)")
                continue
            total_before += before
            total_after += after
            logger.info(
                f"{diary_date}: {format_bytes(before)} -> {format_bytes(after)} "
                f"({100 * (before - after) / before:.0f}% smaller)"
            )

        verb = "would update" if args.dry_run else "updated"
        logger.info(
            f"{verb} {num_updated}, skipped {num_skipped}, failed {num_failed}"
        )
        if total_before:
            logger.info(
                f"total: {format_bytes(total_before)} -> {format_bytes(total_after)} "
                f"(saved {format_bytes(total_before - total_after)}, "
                f"{100 * (total_before - total_after) / total_before:.0f}%)"
            )


if __name__ == "__main__":
    total_start = timer()
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(name)s.%(lineno)d %(levelname)s : %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root_logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.info(" ".join(sys.argv))
    logger.info("{:%Y-%m-%d %H:%M:%S}".format(datetime.now()))
    logger.info("pid: {}".format(os.getpid()))
    import argparse

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--start", help="only days on or after this date (YYYY-MM-DD)")
    parser.add_argument("--end", help="only days on or before this date (YYYY-MM-DD)")
    parser.add_argument("--limit", type=int, help="stop after this many days")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="render and report sizes without touching Joplin or the database",
    )
    parser.add_argument("--debug", action="store_true", help="output debugging info")
    global args
    args = parser.parse_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logging.getLogger("mydiary").setLevel(logging.DEBUG)
        logger.debug("debug mode is on")
    main(args)
    total_end = timer()
    logger.info(
        "all finished. total time: {}".format(format_timespan(total_end - total_start))
    )
