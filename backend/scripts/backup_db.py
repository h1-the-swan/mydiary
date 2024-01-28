# -*- coding: utf-8 -*-

DESCRIPTION = """create a backup of the sqlite database"""

import sys, os, time, shutil, platform
import requests
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

from alembic.migration import MigrationContext
from mydiary.db import sqlite_file_name, rootdir, engine, MydiaryDatabaseBackup, Session


def save_to_nextcloud(fp: Path):
    from mydiary.nextcloud_connector import MyDiaryNextcloud, NEXTCLOUD_USERNAME

    ncld = MyDiaryNextcloud()
    url = f"{ncld.url}/remote.php/dav/files/{NEXTCLOUD_USERNAME}/mydiary/db/{fp.name}"
    with fp.open("rb") as f:
        r = requests.put(url=url, data=f, auth=ncld.auth)


def main(args):
    logger.info(f"creating backup of file {sqlite_file_name}")
    # get alembic version (db migration info)
    context = MigrationContext.configure(engine.connect())
    current_rev = context.get_current_revision()
    # backup file
    backup_dir = Path(rootdir).joinpath("db_backup")
    if not backup_dir.exists():
        backup_dir.mkdir()
    now = pendulum.now()
    backup_fp = backup_dir.joinpath(
        f"database_backup{now.strftime('%Y%m%dT%H%M%S')}_alembic{current_rev}.db"
    )
    logger.info(f"backup filename: {backup_fp}")
    hostname = os.getenv("HOSTNAME") or platform.node()
    logger.info("adding database entry")
    with Session(engine) as session:
        db_obj = MydiaryDatabaseBackup(
            filename=backup_fp.name,
            created_at=now,
            alembic_rev=current_rev,
            hostname=hostname,
            size=os.path.getsize(backup_fp),
        )
        session.add(db_obj)
        session.commit()
    shutil.copyfile(sqlite_file_name, str(backup_fp))
    logger.info("saving to nextcloud")
    save_to_nextcloud(backup_fp)


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
