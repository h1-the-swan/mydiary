# -*- coding: utf-8 -*-

DESCRIPTION = """Get all pocket articles from API and save to database"""

import sys, os, time, json
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from mydiary.models import PocketArticle
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

from mydiary.db import engine, Session, select
from mydiary.pocket_connector import MyDiaryPocket


def main(args):
    with Session(engine) as session:
        mydiary_pocket = MyDiaryPocket()
        num_existing = 0
        num_added = 0
        for i, article in enumerate(mydiary_pocket.yield_all_articles_from_api()):
            existing = session.get(PocketArticle, int(article.id))
            if existing is not None:
                num_existing += 1
                continue
            # article.collect_tags(session=session)
            session.merge(article)
            num_added += 1
            if num_added % 500 == 0:
                logger.debug(f"{num_added} articles added. committing")
                session.commit()
        logger.debug(
            f"finished all articles. num_added={num_added}. skipping {num_existing} because they were already in the database. committing..."
        )
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
