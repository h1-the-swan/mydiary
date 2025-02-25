# -*- coding: utf-8 -*-

DESCRIPTION = """initialize or update journal entries in Joplin for a given date range (one per day). The date range is inclusive (i.e. both start_date and end_date will be included)"""

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
from mydiary.core import get_last_timezone
from mydiary.db import Session, engine

# JOPLIN_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"
# JOPLIN_NOTEBOOK_ID = "b2494842bba94ef3b429f682c4e3386f"


def parse_date(date_str: str, tz: str) -> pendulum.DateTime:
    if date_str == "today":
        return pendulum.today(tz=tz)
    elif date_str == "yesterday":
        return pendulum.yesterday(tz=tz)
    else:
        return pendulum.parse(date_str, tz=tz)


def main(args):
    with Session(engine) as session:
        if args.timezone == "infer":
            tz = get_last_timezone(args.start_date, session=session)
            logger.debug(f"inferred tz: {tz}")
        else:
            tz = args.timezone
        dt = parse_date(args.start_date, tz=tz)

        with MyDiaryJoplin(init_config=False) as mydiary_joplin:
            i = 0
            while True:
                if i == 0:
                    spotify_sync = True
                else:
                    spotify_sync = False

                if args.timezone == "infer":
                    new_tz = get_last_timezone(dt.to_date_string(), session=session)
                    if new_tz != tz:
                        tz = new_tz
                        logger.debug(f"inferred tz: {tz}")
                        dt = parse_date(dt.to_date_string(), tz=tz)
                day = MyDiaryDay.from_dt(
                    dt, spotify_sync=spotify_sync, joplin_connector=mydiary_joplin, session=session
                )

                logger.info(
                    f"initializing or updating Joplin note for day: {dt.to_date_string()}..."
                )
                day.init_or_update_joplin_note()

                if dt.is_same_day(parse_date(args.end_date, tz=tz)) or dt.is_future():
                    break
                
                dt = dt.add(days=1)
                i += 1


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
    logging.getLogger("mydiary").setLevel(logging.INFO)
    logger.info(" ".join(sys.argv))
    logger.info("{:%Y-%m-%d %H:%M:%S}".format(datetime.now()))
    logger.info("pid: {}".format(os.getpid()))
    import argparse

    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument(
        "start_date",
        help='provide a start date in format YYYY-MM-DD or use "today" or "yesterday".',
    )
    parser.add_argument(
        "end_date",
        help='provide an end date in format YYYY-MM-DD or use "today" or "yesterday".',
    )
    parser.add_argument(
        "--timezone",
        "--tz",
        default="America/New_York",
        help='Specify which timezone to use. Default: "America/New_York"',
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
