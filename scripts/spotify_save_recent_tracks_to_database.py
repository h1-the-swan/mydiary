# -*- coding: utf-8 -*-

DESCRIPTION = """Get 50 recently played tracks from the spotify API, and save them to the database"""

import sys, os, time
from pathlib import Path
from datetime import datetime
import pendulum
from timeit import default_timer as timer

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

from mydiary.spotify_connector import MyDiarySpotify
from sqlmodel import Session, select
from mydiary.spotify_history import SpotifyTrackHistory, SpotifyTrackHistoryCreate
from mydiary.db import engine


def main(args):
    mydiary_spotify = MyDiarySpotify()
    recent_tracks = mydiary_spotify.sp.current_user_recently_played()['items']
    with Session(engine) as session:
        num_added = 0
        num_skipped = 0
        for t in recent_tracks:
            spotify_track = SpotifyTrackHistoryCreate.from_spotify_track(t)
            stmt = (
                select(SpotifyTrackHistory)
                .where(SpotifyTrackHistory.spotify_id == spotify_track.spotify_id)
                .where(SpotifyTrackHistory.played_at == spotify_track.played_at)
            )
            existing_row = session.exec(stmt).one_or_none()
            if existing_row:
                num_skipped += 1
                continue
            session.add(SpotifyTrackHistory.from_orm(spotify_track))
            num_added += 1
        logger.debug(f"skipped {num_skipped} tracks because they were already in the database")
        logger.info(f"adding {num_added} new rows to database")
        session.commit()


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
    root_logger.setLevel(logging.INFO)
    logger.info(" ".join(sys.argv))
    logger.info("{:%Y-%m-%d %H:%M:%S}".format(datetime.now()))
    logger.info("pid: {}".format(os.getpid()))
    import argparse

    parser = argparse.ArgumentParser(description=DESCRIPTION)
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
