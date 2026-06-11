from pathlib import Path
from io import BytesIO

import pytest
from PIL import Image

from mydiary.core import get_hash_from_txt, reduce_image_size, reduce_size_recurse

IMAGE_NAME = "24-05-18 13-50-28 9143.jpg"


def test_get_hash_from_txt_deterministic():
    assert get_hash_from_txt("hello world") == get_hash_from_txt("hello world")


def test_get_hash_from_txt_differs_on_different_input():
    assert get_hash_from_txt("hello") != get_hash_from_txt("world")


def test_reduce_image_size(rootdir):
    original = Path(rootdir).joinpath("images", IMAGE_NAME).read_bytes()
    reduced = reduce_image_size(original, size=(64, 64))

    assert len(reduced) < len(original)

    im = Image.open(BytesIO(reduced))
    assert im.size[0] <= 64
    assert im.size[1] <= 64


def test_reduce_size_recurse_stays_under_threshold(rootdir):
    original = Path(rootdir).joinpath("images", IMAGE_NAME).read_bytes()
    threshold = 20000
    result = reduce_size_recurse(original, (512, 512), threshold)
    assert len(result) <= threshold
