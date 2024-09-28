# -*- coding: utf-8 -*-

DESCRIPTION = """core.py"""

import sys, os, time
from typing import Tuple
import requests
import json
import hashlib
from pathlib import Path
from PIL import Image, ImageOps
from io import BytesIO
import pendulum
from sqlmodel import Session, desc, select

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())

# from pocket import Pocket

JOPLIN_BASE_URL = os.environ.get("JOPLIN_BASE_URL") or "http://localhost:41184"
JOPLIN_AUTH_TOKEN = os.environ.get("JOPLIN_AUTH_TOKEN")


def reduce_image_size(
    data: bytes,
    size: Tuple[int, int] = (512, 512),
) -> BytesIO:
    im = Image.open(BytesIO(data))
    format = im.format
    # https://stackoverflow.com/questions/63947990/why-are-width-and-height-of-an-image-are-inverted-when-loading-using-pil-versus
    im = ImageOps.exif_transpose(im)
    im.thumbnail(size)
    image_bytes = BytesIO()
    im.save(image_bytes, format=format)
    return image_bytes.getvalue()


def reduce_size_recurse(data, size: Tuple[int, int], bytes_threshold: int = 60000):
    logger.debug(f"reducing image using size parameter: {size}")
    new_data = reduce_image_size(data, size)
    if len(new_data) > bytes_threshold:
        size = (int(size[0] * 0.9), int(size[1] * 0.9))
        logger.debug(
            f"tried to reduce image size but new image ({len(new_data)} bytes) is still over threshold ({bytes_threshold} bytes). trying again with size parameter {size}"
        )
        return reduce_size_recurse(data, size, bytes_threshold)
    else:
        logger.debug(f"reduced image to {len(new_data)} bytes")
        return new_data


def get_last_timezone(dt_str: str, session: Session) -> str:
    from .models import TimeZoneChange

    dt_obj = pendulum.parse(dt_str)
    z = session.exec(
        select(TimeZoneChange)
        .where(TimeZoneChange.changed_at < dt_obj.end_of("day"))
        .order_by(desc(TimeZoneChange.changed_at))
    ).first()
    if z is None:
        # take the earliest one instead
        z = session.exec(
            select(TimeZoneChange).order_by(TimeZoneChange.changed_at)
        ).first()
        return z.tz_before
    else:
        return z.tz_after
