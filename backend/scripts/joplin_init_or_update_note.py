# -*- coding: utf-8 -*-

DESCRIPTION = """initialize a journal entry in Joplin for a day, or update it if it already exists"""

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

# JOPLIN_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"
# JOPLIN_NOTEBOOK_ID = "b2494842bba94ef3b429f682c4e3386f"


def main(args):
    if args.date == "today":
        dt = pendulum.today(tz=args.timezone)
    elif args.date == "yesterday":
        dt = pendulum.yesterday(tz=args.timezone)
    else:
        dt = pendulum.parse(args.date, tz=args.timezone)

    with MyDiaryJoplin(init_config=False) as mydiary_joplin:
        day = MyDiaryDay.from_dt(dt, joplin_connector=mydiary_joplin)
        day.init_or_update_joplin_note()


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
