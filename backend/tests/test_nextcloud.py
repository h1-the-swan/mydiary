import os
import io
import pendulum
import pytest

from PIL import Image, UnidentifiedImageError

from mydiary.nextcloud_connector import MyDiaryNextcloud


def verify_img_file(image_bytes: bytes):
    # helper function
    try:
        data = io.BytesIO(image_bytes)
        im = Image.open(data, formats=None)
        return True
    except UnidentifiedImageError:
        return False


def test_env_loaded():
    assert "NEXTCLOUD_URL" in os.environ
    assert "NEXTCLOUD_PASSWORD" in os.environ


@pytest.mark.external_api
def test_image_preview():
    path_to_file = "H1phone_sync/2022/06/22-06-24 19-07-01 4885.jpg"
    mydiary_nextcloud = MyDiaryNextcloud()
    image_bytes = mydiary_nextcloud.get_image_thumbnail(path_to_file)
    assert verify_img_file(image_bytes) is True


@pytest.mark.external_api
def test_get_filepaths_for_day():
    mydiary_nextcloud = MyDiaryNextcloud()
    dt = pendulum.parse("2022-06-24")
    hrefs = mydiary_nextcloud.get_filepaths_for_day(
        dt, basedir="H1phone_sync", mimetype_type="image"
    )
    assert len(hrefs) > 0
    for href in hrefs:
        assert href.lower().endswith(".jpg") or href.lower().endswith(".jpeg")


@pytest.mark.external_api
def test_webdav_write_roundtrip(rootdir):
    """upload_file / mkdirs / file_exists / get_image / delete_file round-trip."""
    from pathlib import Path
    from requests.utils import quote

    mydiary_nextcloud = MyDiaryNextcloud()
    image_bytes = (
        Path(rootdir).joinpath("images/24-05-18 13-50-28 9143.jpg").read_bytes()
    )
    test_dir = f"mydiary_uploads/pytest/{pendulum.now().format('YYYYMMDDHHmmss')}"
    filename = "test upload.jpg"  # space exercises percent-encoding
    path = f"{test_dir}/{quote(filename)}"
    created = []
    try:
        mydiary_nextcloud.mkdirs(test_dir)
        # mkdirs is idempotent (405 on existing collections)
        mydiary_nextcloud.mkdirs(test_dir)
        assert mydiary_nextcloud.file_exists(path) is False
        mydiary_nextcloud.upload_file(path, image_bytes)
        created.append(path)
        assert mydiary_nextcloud.file_exists(path) is True
        roundtrip = mydiary_nextcloud.get_image(path)
        assert roundtrip == image_bytes
        assert verify_img_file(roundtrip) is True
    finally:
        for p in created:
            mydiary_nextcloud.delete_file(p)
        mydiary_nextcloud.delete_file(test_dir)
    assert mydiary_nextcloud.file_exists(path) is False
