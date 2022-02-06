# -*- coding: utf-8 -*-

DESCRIPTION = (
    """create a backup of the sqlite database, then recreate an empty database"""
)

import sys, os, time, shutil
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

from mydiary.db import engine, Session, select, create_db_and_tables, sqlite_file_name
from mydiary.spotify_history import SpotifyTrackHistory, SpotifyTrackHistoryCreate


def main(args):
    backup_fp = Path(sqlite_file_name).with_name(f"database_backup{pendulum.now().strftime('%Y%m%dT%H%M%S')}.db")
    logger.info(f"creating backup of file {sqlite_file_name}")
    logger.info(f"backup filename: {backup_fp}")
    shutil.copyfile(sqlite_file_name, str(backup_fp))

    logger.info(f"removing database file: {sqlite_file_name}")
    os.remove(sqlite_file_name)
    logger.info("recreating database (empty)")
    create_db_and_tables(engine)


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

