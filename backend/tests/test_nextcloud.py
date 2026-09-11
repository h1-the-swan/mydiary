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


def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")


@pytest.mark.parametrize(
    "filepath, expected",
    [
        # camera counter lands in the fractional seconds; existing rows rely on it
        ("H1phone_sync/2026/07/26-07-15%2018-33-23%204230.jpg", "2026-07-15T18:33:23.423000"),
        ("H1phone_sync/2023/12/23-12-10%2011-38-04%20zed_.jpg", "2023-12-10T11:38:04.000000"),
        # short counters from a batch saved within one second
        ("H1phone_sync/2026/09/26-09-06%2015-01-25%2045.jpg", "2026-09-06T15:01:25.004500"),
        ("H1phone_sync/2026/09/26-09-06%2015-01-25%201.jpg", "2026-09-06T15:01:25.000100"),
        ("H1phone_sync/2026/09/26-09-06%2015-01-25.jpg", "2026-09-06T15:01:25.000000"),
    ],
)
def test_parse_datetime_from_filepath(filepath, expected):
    dt = MyDiaryNextcloud().parse_datetime_from_filepath(filepath)
    assert _fmt(dt) == expected


def test_parse_datetime_from_filepath_rejects_other_names():
    with pytest.raises(ValueError):
        MyDiaryNextcloud().parse_datetime_from_filepath("H1phone_sync/2026/09/IMG_4230.jpg")


class FakePropfind:
    def __init__(self, names):
        responses = "".join(
            f"<d:response><d:href>/remote.php/dav/files/admin/H1phone_sync/2026/09/{n}</d:href>"
            "<d:propstat><d:prop><d:getcontenttype>image/jpeg</d:getcontenttype></d:prop></d:propstat>"
            "</d:response>"
            for n in names
        )
        self.text = f'<d:multistatus xmlns:d="DAV:">{responses}</d:multistatus>'

    def raise_for_status(self):
        pass


def test_get_filepaths_for_day_skips_unparseable_names(monkeypatch, caplog):
    """The PROPFIND lists the whole month; one odd name must not break every day."""
    names = [
        "26-09-06%2015-01-25%2045.jpg",
        "IMG_4230.jpg",
        "26-09-08%2009-00-00%204301.jpg",
    ]
    monkeypatch.setattr(
        "mydiary.nextcloud_connector.requests.request",
        lambda **kwargs: FakePropfind(names),
    )
    mydiary_nextcloud = MyDiaryNextcloud(url="https://nextcloud.invalid")
    assert mydiary_nextcloud.get_filepaths_for_day(pendulum.datetime(2026, 9, 8)) == [
        "H1phone_sync/2026/09/26-09-08%2009-00-00%204301.jpg"
    ]
    assert mydiary_nextcloud.get_filepaths_for_day(pendulum.datetime(2026, 9, 6)) == [
        "H1phone_sync/2026/09/26-09-06%2015-01-25%2045.jpg"
    ]
    assert "IMG_4230.jpg" in caplog.text


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
