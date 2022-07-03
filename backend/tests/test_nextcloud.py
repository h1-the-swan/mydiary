import os
import io
import pendulum

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


def test_image_preview():
    path_to_file = "H1phone_sync/2022/06/22-06-24 19-07-01 4885.jpg"
    mydiary_nextcloud = MyDiaryNextcloud()
    image_bytes = mydiary_nextcloud.get_image_thumbnail(path_to_file)
    assert verify_img_file(image_bytes) is True


def test_get_filepaths_for_day():
    mydiary_nextcloud = MyDiaryNextcloud()
    dt = pendulum.parse("2022-06-24")
    hrefs = mydiary_nextcloud.get_filepaths_for_day(
        dt, basedir="H1phone_sync", mimetype_type="image"
    )
    assert len(hrefs) > 0
    for href in hrefs:
        assert href.lower().endswith(".jpg") or href.lower().endswith(".jpeg")
