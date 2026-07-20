# -*- coding: utf-8 -*-

DESCRIPTION = """Two-way sync between a set of Nextcloud photo paths and the images section of a Joplin diary note."""

from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

import requests
from sqlmodel import Session, select

from .joplin_connector import MyDiaryJoplin
from .markdown_edits import MarkdownDoc
from .models import JoplinNote, JoplinNoteImageLink, MyDiaryImage
from .nextcloud_connector import MyDiaryNextcloud

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

PHONE_SYNC_BASEDIR = "H1phone_sync"
UPLOADS_BASEDIR = "mydiary_uploads"


def is_upload_path(nextcloud_path: str) -> bool:
    return nextcloud_path.startswith(f"{UPLOADS_BASEDIR}/")


def image_ref(resource_id: str) -> str:
    return f"![](:/{resource_id})"


def sync_note_images(
    session: Session,
    mydiary_joplin: MyDiaryJoplin,
    mydiary_nextcloud: MyDiaryNextcloud,
    note_id: str,
    desired_paths: List[str],
    diary_date: Optional[date] = None,
) -> dict:
    """Make the note's images section match desired_paths (percent-encoded, display order).

    - Paths in desired_paths but not in the note are downloaded, shrunk, uploaded to
      Joplin, recorded in the database, and appended to the images section.
    - Images in the note but not in desired_paths are removed from the section and
      their Joplin resources deleted. iPhone-sync rows are deleted from the database;
      upload rows are kept (with joplin_resource_id nulled) so they remain available
      for re-selection via their diary_date.
    - Resource ids in the note with no MyDiaryImage row (e.g. from the removed Google
      Photos integration) are preserved in place and never touched.
    """
    note = mydiary_joplin.get_note(note_id)
    db_note = session.get(JoplinNote, note_id)
    if db_note is None:
        db_note = session.merge(note)
    md_note = MarkdownDoc(note.body, parent=note)
    sec_images = md_note.get_section_by_title("images")
    current_ids = sec_images.get_resource_ids()

    # resolve existing refs to database rows; unknown ids are left untouched
    id_to_image: Dict[str, Optional[MyDiaryImage]] = {}
    for resource_id in current_ids:
        id_to_image[resource_id] = session.exec(
            select(MyDiaryImage).where(MyDiaryImage.joplin_resource_id == resource_id)
        ).first()
    known_path_to_id = {
        img.nextcloud_path: rid
        for rid, img in id_to_image.items()
        if img is not None and img.nextcloud_path
    }

    # dedupe desired paths, preserving order
    desired = list(dict.fromkeys(desired_paths))
    to_add = [p for p in desired if p not in known_path_to_id]
    to_remove = {
        rid: img
        for rid, img in id_to_image.items()
        if img is not None
        and (not img.nextcloud_path or img.nextcloud_path not in desired)
    }
    if not to_add and not to_remove:
        return {"note_id": note.id, "added": [], "removed": [], "resource_ids": current_ids}

    # create resources for new photos before touching the note
    added_images: List[MyDiaryImage] = []
    new_resource_ids: List[str] = []
    try:
        for photo_path in to_add:
            image_bytes = mydiary_nextcloud.get_image(photo_path)
            image_name = Path(requests.utils.unquote(photo_path)).stem
            try:
                created_at = mydiary_nextcloud.parse_datetime_from_filepath(photo_path)
            except Exception:
                created_at = None
            new_image = mydiary_joplin.create_thumbnail(
                image_bytes,
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
            new_resource_ids.append(new_image.joplin_resource_id)
            logger.debug(f"new resource id: {new_image.joplin_resource_id}")

        # rebuild the section: kept refs in original order (unknown ids stay in
        # place), then newly added refs
        final_refs = [
            rid for rid in current_ids if id_to_image[rid] is None or rid not in to_remove
        ]
        final_refs.extend(new_resource_ids)
        # identical image content shares one Joplin resource id, so the same ref
        # can appear twice; keep the first occurrence only
        final_refs = list(dict.fromkeys(final_refs))
        sec_images.set_content("\n\n".join(image_ref(rid) for rid in final_refs))

        logger.info(f"updating note: {note.title}")
        r_put_note = mydiary_joplin.update_note_body(note.id, md_note.txt)
        r_put_note.raise_for_status()
    except Exception:
        session.rollback()
        for rid in new_resource_ids:
            try:
                mydiary_joplin.delete_resource(rid, force=True)
            except Exception:
                logger.warning(f"failed to clean up joplin resource {rid}")
        raise

    # note update succeeded: now safe to delete removed resources (best-effort)
    for rid in to_remove:
        try:
            r = mydiary_joplin.delete_resource(rid, ignore_id=note.id)
            r.raise_for_status()
        except Exception:
            logger.warning(f"failed to delete joplin resource {rid}; continuing")

    # database bookkeeping, committed in one transaction
    for link in session.exec(
        select(JoplinNoteImageLink).where(JoplinNoteImageLink.joplin_note_id == note.id)
    ).all():
        session.delete(link)
    for rid, img in to_remove.items():
        if img.nextcloud_path and is_upload_path(img.nextcloud_path):
            img.joplin_resource_id = None
            session.add(img)
        else:
            session.delete(img)
    # newly added refs are not in id_to_image; map them from added_images
    added_by_id = {img.joplin_resource_id: img for img in added_images}
    sequence_num = 0
    for rid in final_refs:
        img = id_to_image.get(rid) or added_by_id.get(rid)
        if img is None:  # unknown (legacy) resource id
            continue
        sequence_num += 1
        session.add(
            JoplinNoteImageLink(
                note=db_note,
                mydiary_image=img,
                sequence_num=sequence_num,
                note_title=note.title,
            )
        )
    db_note.body = md_note.txt
    db_note.has_images = len(final_refs) > 0
    session.add(db_note)
    session.commit()

    return {
        "note_id": note.id,
        "added": [img.nextcloud_path for img in added_images],
        "removed": [img.nextcloud_path for img in to_remove.values()],
        "resource_ids": final_refs,
    }
