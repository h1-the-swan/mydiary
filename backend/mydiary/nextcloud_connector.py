# -*- coding: utf-8 -*-

DESCRIPTION = """Nextcloud API"""

import sys, os, time, json, re
import requests
from requests.auth import HTTPBasicAuth
from lxml import etree
from pathlib import Path
from datetime import date, datetime
from time import sleep
import pendulum
from timeit import default_timer as timer
from typing import Any, Collection, Dict, List, Optional, Tuple, Union

from .core import reduce_image_size, reduce_size_recurse
import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

# from dotenv import load_dotenv, find_dotenv

# load_dotenv(find_dotenv())

NEXTCLOUD_URL = os.environ["NEXTCLOUD_URL"]
NEXTCLOUD_USERNAME = os.environ.get("NEXTCLOUD_USERNAME") or "admin"
NEXTCLOUD_PASSWORD = os.environ["NEXTCLOUD_PASSWORD"]


class MyDiaryNextcloud:
    def __init__(self, url=NEXTCLOUD_URL) -> None:
        self.url = url
        self.auth = HTTPBasicAuth(NEXTCLOUD_USERNAME, NEXTCLOUD_PASSWORD)

    def get_image_thumbnail(self, path_to_file: str, w=512, h=512) -> bytes:
        # will automatically scale aspect ratio (because of the query param a=1)
        url = f"{self.url}/index.php/core/preview.png?file={path_to_file}&x={h}pxW&y={w}pxH&a=1&mode=cover&forceIcon=0"
        r = requests.get(url, auth=self.auth)
        r.raise_for_status()
        return r.content

    def parse_datetime_from_filepath(self, filepath: str, tz: str = 'local') -> pendulum.DateTime:
        filepath = requests.utils.unquote(filepath)
        name = Path(filepath).stem
        # name will look like: "22-06-11 17-50-16 4704"
        return pendulum.from_format(name, "YY-MM-DD HH-mm-ss SSSS", tz=tz)

    def get_mimetype_type(self, xml_item) -> str:
        mimetype = xml_item.find(".//{DAV:}getcontenttype")
        if mimetype is not None:
            mimetype_split = mimetype.text.split("/")
            if mimetype_split:
                return mimetype_split[0]
        return ""

    def yield_filepaths_for_day(
        self, dt: datetime, basedir="H1phone_sync", mimetype_type="image"
    ):
        url = f"{self.url}/remote.php/dav/files/{NEXTCLOUD_USERNAME}/{basedir}/{dt.year}/{dt.month:02d}/"
        r = requests.request(method="PROPFIND", url=url, auth=self.auth)
        r.raise_for_status()
        root = etree.fromstring(r.text)
        items = root.findall(".//{DAV:}response")
        for item in items:
            this_mimetype_type = self.get_mimetype_type(item)
            if this_mimetype_type == mimetype_type:
                filepath = item.find("{DAV:}href").text
                this_dt = self.parse_datetime_from_filepath(filepath)
                if this_dt.is_same_day(dt):
                    yield filepath

    def get_filepaths_for_day(
        self, dt: datetime, basedir="H1phone_sync", mimetype_type="image"
    ) -> List[str]:
        return list(
            self.yield_filepaths_for_day(
                dt=dt, basedir=basedir, mimetype_type=mimetype_type
            )
        )
