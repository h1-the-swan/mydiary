# -*- coding: utf-8 -*-

DESCRIPTION = (
    """add existing notes from Joplin to the database if they're not already in there"""
)

import pendulum
import sys, os, time
from pathlib import Path
from datetime import datetime
from timeit import default_timer as timer

try:
    from humanfriendly import format_timespan
except ImportError:

    def format_timespan(seconds):
        return "{:.2f} seconds".format(seconds)


import logging
from mydiary.db import Session, engine, select
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.models import JoplinNote, MyDiaryWords

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


def main(args):
    min_year = 2022
    max_year = pendulum.yesterday().year
    mydiary_joplin = MyDiaryJoplin(init_config=False)
    with Session(engine) as session:
        total_added = 0
        for year in range(min_year, max_year + 1):
            this_year_added = 0
            subfolder_id = mydiary_joplin.get_subfolder_id(str(year))
            fields = [
                "id",
                "parent_id",
                "title",
                "body",
                "created_time",
                "updated_time",
            ]
            now = pendulum.now().in_timezone("UTC")
            logger.info(f"starting year: {year}. subfolder_id: {subfolder_id}")
            for note in mydiary_joplin.yield_notes_by_subfolder_id(
                subfolder_id, fields=fields
            ):
                existing = session.exec(
                    select(JoplinNote).where(JoplinNote.title == note["title"])
                ).one_or_none()
                if existing is not None:
                    # already exists in database. skip
                    continue
                db_note = JoplinNote.from_api_response(note)
                db_note.time_last_api_sync = now
                db_words = MyDiaryWords.from_joplin_note(db_note)
                session.add(db_note)
                session.add(db_words)
                this_year_added += 1
            logger.info(f"adding {this_year_added} entries for year {year}")
            session.commit()
            total_added += this_year_added
        logger.info(f"finished. added {total_added} entries total")


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
        root_logger.setLevel(logging.DEBUG)
        logger.debug("debug mode is on")
    main(args)
    total_end = timer()
    logger.info(
        "all finished. total time: {}".format(format_timespan(total_end - total_start))
    )
