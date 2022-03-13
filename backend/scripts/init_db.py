# -*- coding: utf-8 -*-

DESCRIPTION = (
    """Initialize the database, and load Spotify tracks that were saved as json files"""
)

import sys, os, time, json
from collections import defaultdict
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

from mydiary.db import engine, Session, select, create_db_and_tables
from mydiary.spotify_history import SpotifyTrackHistory, SpotifyTrackHistoryCreate


def main(args):
    spotify_datadir = Path(args.spotify_json_dir)

    # Create db and tables. This will skip tables that already exist.
    create_db_and_tables(engine)

    tracks = []
    for fp in spotify_datadir.glob("spotify_recent_tracks_dump*.json"):
        data = json.loads(fp.read_text())
        items = data["items"]
        for item in items:
            tracks.append(item)
    with Session(engine) as session:
        _unique = defaultdict(set)
        i = 0
        for t in tracks:
            spotify_track = SpotifyTrackHistoryCreate.from_spotify_track(t)
            if spotify_track.spotify_id not in _unique or spotify_track.played_at not in _unique[spotify_track.spotify_id]:
                db_track = SpotifyTrackHistory.from_orm(spotify_track)
                session.add(db_track)
                _unique[spotify_track.spotify_id].add(spotify_track.played_at)
                i += 1
        logger.info(f"adding {i} tracks to spotifytrackhistory table")
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
    parser.add_argument("spotify_json_dir", help="directory with spotify recent tracks dump json files")
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
