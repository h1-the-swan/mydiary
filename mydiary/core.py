# -*- coding: utf-8 -*-

DESCRIPTION = """core.py"""

import sys, os, time
from typing import Tuple
import requests
import json
import hashlib
from pathlib import Path
from PIL import Image
from io import BytesIO

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# from pocket import Pocket

JOPLIN_BASE_URL = os.environ.get("JOPLIN_BASE_URL") or "http://localhost:41184"
JOPLIN_AUTH_TOKEN = os.environ["JOPLIN_AUTH_TOKEN"]



def reduce_image_size(
    data: bytes,
    size: Tuple[int, int] = (512, 512),
) -> BytesIO:
    im = Image.open(BytesIO(data))
    im.thumbnail(size)
    image_bytes = BytesIO()
    im.save(image_bytes, format=im.format)
    return image_bytes

