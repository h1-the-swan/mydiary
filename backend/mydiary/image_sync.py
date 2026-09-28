# -*- coding: utf-8 -*-

DESCRIPTION = """Two-way sync between a set of Nextcloud photo paths and the images section of a Joplin diary note."""

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pendulum
import requests
from sqlmodel import Session, select

from .core import reduce_size_recurse
from .diary_note import DiaryNote, image_resource_ids_of, resource_ref
from .joplin_port import JoplinPort
from .models import MyDiaryImage
from .nextcloud_connector import MyDiaryNextcloud

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

PHONE_SYNC_BASEDIR = "H1phone_sync"
UPLOADS_BASEDIR = "mydiary_uploads"

SECTION_TITLE = "Images"


def is_upload_path(nextcloud_path: str) -> bool:
    return nextcloud_path.startswith(f"{UPLOADS_BASEDIR}/")


def capture_time(
    mydiary_nextcloud: MyDiaryNextcloud, nextcloud_path: Optional[str]
) -> Optional[datetime]:
    """When an iPhone photo was taken, from its filename; None for uploads and
    anything else whose name doesn't carry one."""
    if not nextcloud_path or is_upload_path(nextcloud_path):
        return None
    try:
        return mydiary_nextcloud.parse_datetime_from_filepath(nextcloud_path)
    except Exception:
        return None


def place_by_capture_time(
    current: List[Tuple[str, Optional[datetime]]],
    new: List[Tuple[str, Optional[datetime]]],
) -> List[str]:
    """Merge new refs into the section's current refs, both as (ref, capture time).

    Each new photo with a capture time goes directly after the photo in the
    section with the latest capture time before its own, or, if there is none,
    before the first photo that has a capture time. Refs without one (uploads,
    unknown ids) are never used as neighbours and stay where they are; new ones
    go at the end. The current refs keep their relative order, even if it isn't
    chronological.
    """
    placed = list(current)
    for ref, taken in sorted(
        (item for item in new if item[1] is not None), key=lambda item: item[1]
    ):
        earlier = [
            i for i, (_, t) in enumerate(placed) if t is not None and t <= taken
        ]
        if earlier:
            latest = max(earlier, key=lambda i: (placed[i][1], i))
            index = latest + 1
        else:
            timed = [i for i, (_, t) in enumerate(placed) if t is not None]
            index = timed[0] if timed else len(placed)
        placed.insert(index, (ref, taken))
    timeless = [item for item in new if item[1] is None]
    return [ref for ref, _ in placed + timeless]


@dataclass(frozen=True)
class ShrunkPhoto:
    """A photo made small enough to put in a note."""

    data: bytes
    hash: str  # md5 of `data`, which is also its Joplin resource id
    orig_hash: str  # md5 of the photo as it came in

    def image_row(
        self,
        resource_id: str,
        name: Optional[str] = None,
        nextcloud_path: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ) -> MyDiaryImage:
        if created_at is None:
            created_at = pendulum.now(tz="UTC")
        return MyDiaryImage(
            hash=self.hash,
            name=name,
            filepath=None,
            nextcloud_path=nextcloud_path,
            description=None,
            thumbnail_size=len(self.data),
            joplin_resource_id=resource_id,
            created_at=pendulum.instance(created_at).in_timezone("UTC"),
            orig_image_hash=self.orig_hash,
        )


def shrink_photo(
    image_bytes: bytes,
    size: Tuple[int, int] = (512, 512),
    bytes_threshold: int = 60000,
) -> ShrunkPhoto:
    """Scale a photo down until it's under `bytes_threshold` bytes; one
    already under it is left as it is."""
    orig_hash = hashlib.md5(image_bytes).hexdigest()
    if len(image_bytes) > bytes_threshold:
        image_bytes = reduce_size_recurse(image_bytes, size, bytes_threshold)
    return ShrunkPhoto(
        data=image_bytes,
        hash=hashlib.md5(image_bytes).hexdigest(),
        orig_hash=orig_hash,
    )


def sync_note_images(
    session: Session,
    joplin: JoplinPort,
    mydiary_nextcloud: MyDiaryNextcloud,
    note_id: str,
    desired_paths: List[str],
    diary_date: Optional[date] = None,
    keep_existing: bool = False,
) -> dict:
    """Make the note's images section show exactly desired_paths (percent-encoded).

    - Paths in desired_paths but not in the note are downloaded, shrunk, uploaded to
      Joplin, and recorded in the database. New iPhone photos are placed among the
      section's photos by capture time, and new uploads go at the end (see
      `place_by_capture_time`). Photos already in the note keep their order.
    - Images in the note but not in desired_paths are removed from the section and
      their Joplin resources deleted. iPhone-sync rows are deleted from the database;
      upload rows are kept (with joplin_resource_id nulled) so they remain available
      for re-selection via their diary_date.
    - Resource ids in the note with no MyDiaryImage row (e.g. from the removed Google
      Photos integration) are preserved in place and never touched.

    With `keep_existing`, desired_paths are added to the photos the note
    already shows, and nothing is removed.

    The write goes through `DiaryNote.edit()`, whose mirror refresh rebuilds
    the note's image links from the section it wrote.
    """
    diary_note = DiaryNote.get(joplin, note_id)
    with diary_note.edit(session) as edit:
        current_ids = image_resource_ids_of(edit.note.body)

        # resolve existing refs to database rows; unknown ids are left untouched
        id_to_image: Dict[str, Optional[MyDiaryImage]] = {}
        for resource_id in current_ids:
            id_to_image[resource_id] = session.exec(
                select(MyDiaryImage).where(
                    MyDiaryImage.joplin_resource_id == resource_id
                )
            ).first()
        known_path_to_id = {
            img.nextcloud_path: rid
            for rid, img in id_to_image.items()
            if img is not None and img.nextcloud_path
        }

        if keep_existing:
            desired_paths = list(known_path_to_id) + list(desired_paths)
        # dedupe desired paths, preserving order
        desired = list(dict.fromkeys(desired_paths))
        to_add = [p for p in desired if p not in known_path_to_id]
        to_remove = {
            rid: img
            for rid, img in id_to_image.items()
            if img is not None
            and not keep_existing
            and (not img.nextcloud_path or img.nextcloud_path not in desired)
        }
        if not to_add and not to_remove:
            return {
                "note_id": note_id,
                "added": [],
                "removed": [],
                "resource_ids": current_ids,
            }

        added_images: List[MyDiaryImage] = []
        new_resource_ids: List[str] = []
        for photo_path in to_add:
            image_name = Path(requests.utils.unquote(photo_path)).stem
            try:
                created_at = mydiary_nextcloud.parse_datetime_from_filepath(photo_path)
            except Exception:
                created_at = None
            photo = shrink_photo(mydiary_nextcloud.get_image(photo_path))
            resource_id = edit.add_resource(photo.data, title=image_name)
            new_image = photo.image_row(
                resource_id,
                name=image_name,
                nextcloud_path=photo_path,
                created_at=created_at,
            )
            # reuse an existing row for this path if one exists (e.g. a previously
            # removed upload being re-selected) instead of inserting a duplicate
            existing_row = session.exec(
                select(MyDiaryImage).where(MyDiaryImage.nextcloud_path == photo_path)
            ).first()
            if existing_row is not None:
                existing_row.hash = new_image.hash
                existing_row.thumbnail_size = new_image.thumbnail_size
                existing_row.joplin_resource_id = new_image.joplin_resource_id
                existing_row.orig_image_hash = new_image.orig_image_hash
                new_image = existing_row
            if diary_date is not None and is_upload_path(photo_path):
                new_image.diary_date = diary_date
            session.add(new_image)
            added_images.append(new_image)
            new_resource_ids.append(resource_id)
            logger.debug(f"new resource id: {resource_id}")

        # rebuild the section: kept refs in their original order (unknown ids
        # stay in place), with new photos placed among them by capture time
        kept = [
            (
                rid,
                None
                if id_to_image[rid] is None
                else capture_time(mydiary_nextcloud, id_to_image[rid].nextcloud_path),
            )
            for rid in current_ids
            if id_to_image[rid] is None or rid not in to_remove
        ]
        new = [
            (rid, capture_time(mydiary_nextcloud, path))
            for rid, path in zip(new_resource_ids, to_add)
        ]
        final_refs = place_by_capture_time(kept, new)
        # identical image content shares one Joplin resource id, so the same ref
        # can appear twice; keep the first occurrence only
        final_refs = list(dict.fromkeys(final_refs))
        edit.set_section(
            SECTION_TITLE, "\n\n".join(resource_ref(rid) for rid in final_refs)
        )

        for rid, img in to_remove.items():
            edit.drop_resource(rid)
            if img.nextcloud_path and is_upload_path(img.nextcloud_path):
                img.joplin_resource_id = None
                session.add(img)
                continue
            if any(link.joplin_note_id != note_id for link in img.note_links):
                # another day shows the same photo; deleting the row would
                # turn its ref there into an unknown one
                continue
            # its links go first, as they can't outlive the row
            for link in img.note_links:
                session.delete(link)
            session.delete(img)
        logger.info(f"updating note: {edit.note.title}")

    return {
        "note_id": note_id,
        "added": [img.nextcloud_path for img in added_images],
        "removed": [img.nextcloud_path for img in to_remove.values()],
        "resource_ids": final_refs,
    }
