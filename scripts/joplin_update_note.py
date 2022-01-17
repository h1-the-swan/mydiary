# -*- coding: utf-8 -*-

DESCRIPTION = """Update a journal entry in Joplin for a day with new info (e.g., newly created events in Google calendar)"""

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

from mydiary import MyDiaryDay
from mydiary.joplin_connector import MyDiaryJoplin
from mydiary.markdown_edits import MarkdownDoc

# JOPLIN_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"


def main(args):
    if args.date == "today":
        dt = pendulum.today(tz=args.timezone)
    elif args.date == "yesterday":
        dt = pendulum.yesterday(tz=args.timezone)
    else:
        dt = pendulum.parse(args.date, tz=args.timezone)

    with MyDiaryJoplin(init_config=False) as mydiary_joplin:
        logger.info("starting Joplin sync")
        mydiary_joplin.sync()
        logger.info("sync complete")
        day = MyDiaryDay.from_dt(dt, joplin_connector=mydiary_joplin)

        existing_id = day.get_joplin_note_id()
        if not existing_id:
            raise RuntimeError(
                f"Joplin note does not already exist for date {dt.to_date_string()}!"
            )
        note = mydiary_joplin.get_note(existing_id)
        md_note = MarkdownDoc(note.body, parent=note)
        md_new = MarkdownDoc(day.init_markdown())

        need_to_update = False
        for sec in md_note.sections:
            try:
                update_txt = md_new.get_section_by_title(sec.title).txt
            except KeyError:
                logger.debug(f"section {sec.title} not found in new text. skipping")
                continue
            result = sec.update(update_txt)
            if result == "updated":
                need_to_update = True
            logger.debug(f"section {sec.title}: {result}")

        if need_to_update is True:
            logger.info(f"updating note: {note.title}")
            r_put_note = mydiary_joplin.update_note_body(note.id, md_note.txt)
            logger.info(f"done. status code: {r_put_note.status_code}")

            logger.info("starting Joplin sync")
            mydiary_joplin.sync()
            logger.info("sync complete")

        else:
            logger.info("no updates made")


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
    parser.add_argument(
        "date",
        nargs="?",
        default="today",
        help='provide a date in format YYYY-MM-DD or use "today" or "yesterday". Default: "today"',
    )
    parser.add_argument(
        "--timezone",
        "--tz",
        default="local",
        help='Specify which timezone to use (e.g. "America/Los_Angeles"). Default: "local"',
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
