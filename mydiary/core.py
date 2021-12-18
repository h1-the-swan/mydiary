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


def joplin_create_resource(
    data: bytes, title: str = None, ext: str = "jpg", token: str = JOPLIN_AUTH_TOKEN
) -> requests.Response:
    hash = hashlib.md5()
    hash.update(data)
    if title is None:
        title = hash.hexdigest()
    if ext and ext.startswith("."):
        ext = ext[1:]
    props = {
        "id": hash.hexdigest(),
        "filename": f"{hash.hexdigest()}.{ext}",
        "title": title,
    }
    response = requests.post(
        f"{JOPLIN_BASE_URL}/resources",
        files={
            "data": (
                f"{hash.hexdigest()}.{ext}",
                data,
                "multipart/form-data",
            )
        },
        data={"props": json.dumps(props)},
        params={"token": token},
    )
    return response


def reduce_image_size(
    data: bytes,
    size: Tuple[int, int] = (512, 512),
) -> BytesIO:
    im = Image.open(BytesIO(data))
    im.thumbnail(size)
    image_bytes = BytesIO()
    im.save(image_bytes, format=im.format)
    return image_bytes


def joplin_reduce_image_size(
    resource_id: str,
    token: str = JOPLIN_AUTH_TOKEN,
    size: Tuple[int, int] = (512, 512),
    delete_original: bool = True,
) -> None:
    resource_file = requests.get(
        f"{JOPLIN_BASE_URL}/resources/{resource_id}/file", params={"token": token}
    )
    image_bytes = reduce_image_size(resource_file.content, size)
    r = joplin_create_resource(data=image_bytes.getvalue(), token=token)
    if delete_original is True:
        requests.delete(
            f"{JOPLIN_BASE_URL}/resources/{resource_id}", params={"token": token}
        )
    return r
