# -*- coding: utf-8 -*-

DESCRIPTION = """initialize a journal entry in Joplin for today"""

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

JOPLIN_NOTEBOOK_ID = "84f655fb941440d78f993adc8bb731b3"

def main(args):
    try:
        mydiary_joplin = MyDiaryJoplin()
        if not mydiary_joplin.server_is_running():
            logger.debug("starting Joplin server")
            mydiary_joplin.start_server()

        logger.debug("starting Joplin sync")
        mydiary_joplin.sync()
        logger.debug("sync complete")

        today = pendulum.today()
        day = MyDiaryDay.from_dt(today)
        data = {
            'id': day.uid.hex,
            'parent_id': JOPLIN_NOTEBOOK_ID,
            'title': day.dt.strftime("%Y-%m-%d"),
            'body': day.init_markdown(),
        }
        logger.debug(f"creating note: {data['title']}")
        r_post_note = mydiary_joplin.post_note(data)
        logger.debug(f"done. status code: {r_post_note.status_code}")

        logger.debug("starting Joplin sync")
        mydiary_joplin.sync()
        logger.debug("sync complete")
    finally:
        mydiary_joplin.teardown()

if __name__ == "__main__":
    total_start = timer()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt="%(asctime)s %(name)s.%(lineno)d %(levelname)s : %(message)s", datefmt="%H:%M:%S"))
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    logger.info(" ".join(sys.argv))
    logger.info( '{:%Y-%m-%d %H:%M:%S}'.format(datetime.now()) )
    logger.info("pid: {}".format(os.getpid()))
    import argparse
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument("--debug", action='store_true', help="output debugging info")
    global args
    args = parser.parse_args()
    if args.debug:
        root_logger.setLevel(logging.DEBUG)
        logger.debug('debug mode is on')
    main(args)
    total_end = timer()
    logger.info('all finished. total time: {}'.format(format_timespan(total_end-total_start)))