# -*- coding: utf-8 -*-

DESCRIPTION = """Tags: what they can be attached to, and what they may refer to.

A tag is `#slug` or `#namespace:slug` (see `hashtags.py` for the grammar). It
can be attached to anything through `TagLink`, and its namespace can refer to
a kind of thing that has a table. Both ideas share one registry, ENTITY_KINDS:
an entry is at once a *target type* (a song can carry tags) and a *namespace*
(`#song:wonderwall` names a song). An entry with no `resolve` is a target type
only; a namespace with no entry at all is perfectly valid, it just never
resolves. That is the point: you can start writing `#book:...` today, and if a
Book table appears later the existing tags light up without any migration,
because resolution is computed when a tag is read and never stored.

Links are stored, with a `source`: "note" for a hashtag in the note body,
"joplin" for one of Joplin's own note-level tags (one way, Joplin -> here),
"manual" for the API and the UI, "pocket" for an imported article tag. The
primary key of a link does not include the source, so every writer only
*ensures* a link exists and only removes links of its own source: a manual
link outlives the hashtag, and a note link outlives a manual removal until the
hashtag itself goes.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlmodel import Session, select

from .hashtags import parse_hashtags, parse_key, slugify_tag
from .models import Dog, JoplinNote, PerformSong, PocketArticle, Recipe, Tag, TagLink

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)

SOURCE_NOTE = "note"  # a hashtag in the note body
SOURCE_JOPLIN = "joplin"  # one of Joplin's own note-level tags
SOURCE_MANUAL = "manual"  # set through the API or the UI
SOURCE_POCKET = "pocket"  # imported with a Pocket article

# the target type a note's hashtags attach to; target_id is the note title (YYYY-MM-DD)
DAY = "day"


class UnknownTargetType(ValueError):
    """The target_type is not a key in ENTITY_KINDS."""


# --- the registry ----------------------------------------------------------


@dataclass(frozen=True)
class EntityKind:
    """One kind of thing tags can attach to, and optionally refer to.

    `get`, `display` and `resolve` take the kind itself first, so the defaults
    can be shared functions rather than per-kind closures."""

    key: str  # the namespace and the target_type, e.g. "dog"
    model: Any
    label: str  # "Dog": what the UI shows
    plural: str  # "Dogs"
    id_of: Callable[[Any], str]
    get: Callable[["EntityKind", Session, str], Optional[Any]]
    display: Callable[[Any], str]
    # slug -> row, or None when nothing (or more than one thing) matches.
    # None means the namespace is not resolvable: a target type only.
    resolve: Optional[Callable[["EntityKind", Session, str], Optional[Any]]]
    # vue-router route name that shows one of these, if a page exists
    frontend_route: Optional[str] = None


def _id_of_pk(row: Any) -> str:
    return str(row.id)


def _get_by_pk(kind: EntityKind, session: Session, target_id: str) -> Optional[Any]:
    try:
        pk = int(target_id)
    except ValueError:
        return None
    return session.get(kind.model, pk)


def _safe_slug(text: Optional[str]) -> Optional[str]:
    try:
        return slugify_tag(text or "")
    except ValueError:
        return None


def resolve_by_display_slug(
    kind: EntityKind, session: Session, slug: str
) -> Optional[Any]:
    """The default resolver: the one row whose slugified display name is the slug.

    Reads the whole table, which is fine for the tables registered here. A
    kind that outgrows that (or gains a real slug column) supplies its own."""
    matches = [
        row
        for row in session.exec(select(kind.model)).all()
        if _safe_slug(kind.display(row)) == slug
    ]
    return matches[0] if len(matches) == 1 else None


def _get_day(kind: EntityKind, session: Session, target_id: str) -> Any:
    # a day exists whether or not its note has been mirrored yet, so a manual
    # tag on an unmirrored day still shows up; the stand-in only needs `title`
    row = session.exec(select(JoplinNote).where(JoplinNote.title == target_id)).first()
    return row if row is not None else SimpleNamespace(title=target_id)


def _resolve_day(kind: EntityKind, session: Session, slug: str) -> Optional[Any]:
    return session.exec(select(JoplinNote).where(JoplinNote.title == slug)).first()


def _article_title(row: PocketArticle) -> str:
    return row.resolved_title or row.given_title or "Unknown title"


ENTITY_KINDS: Dict[str, EntityKind] = {
    kind.key: kind
    for kind in [
        EntityKind(
            key=DAY,
            model=JoplinNote,
            label="Day",
            plural="Days",
            id_of=lambda row: row.title,
            get=_get_day,
            display=lambda row: row.title,
            resolve=_resolve_day,
            frontend_route="MyDiaryDay",
        ),
        EntityKind(
            key="dog",
            model=Dog,
            label="Dog",
            plural="Dogs",
            id_of=_id_of_pk,
            get=_get_by_pk,
            display=lambda row: row.name,
            resolve=resolve_by_display_slug,
        ),
        EntityKind(
            key="recipe",
            model=Recipe,
            label="Recipe",
            plural="Recipes",
            id_of=_id_of_pk,
            get=_get_by_pk,
            display=lambda row: row.name,
            resolve=resolve_by_display_slug,
        ),
        EntityKind(
            key="song",
            model=PerformSong,
            label="Song",
            plural="Songs",
            id_of=_id_of_pk,
            get=_get_by_pk,
            display=lambda row: row.name,
            resolve=resolve_by_display_slug,
            frontend_route="performSong",
        ),
        EntityKind(
            key="article",
            model=PocketArticle,
            label="Article",
            plural="Articles",
            id_of=_id_of_pk,
            get=_get_by_pk,
            display=_article_title,
            resolve=None,
        ),
    ]
}


def kind_for(target_type: str) -> EntityKind:
    try:
        return ENTITY_KINDS[target_type]
    except KeyError:
        raise UnknownTargetType(
            f"unknown target type {target_type!r}; known: {sorted(ENTITY_KINDS)}"
        )


def namespace_label(namespace: str) -> Tuple[str, str]:
    """(singular, plural) label for a namespace, registered or not."""
    kind = ENTITY_KINDS.get(namespace)
    if kind is not None:
        return kind.label, kind.plural
    if not namespace:
        return "Tag", "Tags"
    word = namespace.replace("-", " ").replace("_", " ").title()
    return word, word + "s"


# --- tags -----------------------------------------------------------------


def get_or_create_tag(
    session: Session,
    namespace: str,
    slug: str,
    name: Optional[str] = None,
    commit: bool = True,
) -> Tag:
    tag = session.exec(
        select(Tag).where(Tag.namespace == namespace, Tag.slug == slug)
    ).one_or_none()
    if tag is None:
        tag = Tag(namespace=namespace, slug=slug, name=name or slug)
        session.add(tag)
        session.flush()
        if commit:
            session.commit()
    return tag


def tag_by_key(session: Session, key: str) -> Optional[Tag]:
    namespace, slug = parse_key(key)
    return session.exec(
        select(Tag).where(Tag.namespace == namespace, Tag.slug == slug)
    ).one_or_none()


def delete_tag(session: Session, tag: Tag, commit: bool = True) -> None:
    # explicit, because SQLite is not enforcing the foreign key
    for link in session.exec(select(TagLink).where(TagLink.tag_id == tag.id)).all():
        session.delete(link)
    session.delete(tag)
    if commit:
        session.commit()


def tag_link_counts(session: Session) -> Dict[int, int]:
    rows = session.exec(
        select(TagLink.tag_id, func.count()).group_by(TagLink.tag_id)
    ).all()
    return {tag_id: n for tag_id, n in rows}


def namespaces(session: Session) -> List[Tuple[str, int]]:
    """Every namespace with its tag count: the registered kinds always, even
    at zero, so their labels are known; anything else only once it has a tag.
    "" (no namespace) sorts first."""
    counts = dict(
        session.exec(select(Tag.namespace, func.count()).group_by(Tag.namespace)).all()
    )
    names = set(counts) | set(ENTITY_KINDS) | {""}
    return [(ns, counts.get(ns, 0)) for ns in sorted(names)]


# --- links ----------------------------------------------------------------


def _links_with_tags(
    session: Session, target_type: str, target_id: str
) -> List[Tuple[TagLink, Tag]]:
    return session.exec(
        select(TagLink, Tag)
        .join(Tag, Tag.id == TagLink.tag_id)
        .where(TagLink.target_type == target_type, TagLink.target_id == target_id)
        .order_by(Tag.namespace, Tag.slug)
    ).all()


def tags_for_target(
    session: Session, target_type: str, target_id: str
) -> List[Tuple[Tag, str]]:
    """The tags on one thing, each with the source of its link."""
    kind_for(target_type)
    return [(tag, link.source) for link, tag in _links_with_tags(session, target_type, target_id)]


def tags_for_targets(
    session: Session, target_type: str, target_ids: Iterable[str]
) -> Dict[str, List[Tag]]:
    """The tags on many things of one kind, in one query. Every id gets a key."""
    kind_for(target_type)
    ids = [str(i) for i in target_ids]
    out: Dict[str, List[Tag]] = {i: [] for i in ids}
    if not ids:
        return out
    rows = session.exec(
        select(TagLink.target_id, Tag)
        .join(Tag, Tag.id == TagLink.tag_id)
        .where(TagLink.target_type == target_type, TagLink.target_id.in_(ids))
        .order_by(Tag.namespace, Tag.slug)
    ).all()
    for target_id, tag in rows:
        out[target_id].append(tag)
    return out


def _ensure_links(
    session: Session,
    target_type: str,
    target_id: str,
    wanted: Dict[Tuple[str, str], Optional[str]],
    source: str,
    remove_source: Callable[[str], bool],
) -> Tuple[int, int]:
    """Bring a target's links in line with `wanted` {(namespace, slug): name}.

    Existing links are kept whatever their source; missing ones are added with
    `source`; links whose key is not wanted are removed only when
    `remove_source(link.source)` says that source is ours to remove."""
    existing = {
        (tag.namespace, tag.slug): link
        for link, tag in _links_with_tags(session, target_type, target_id)
    }
    added = removed = 0
    for (namespace, slug), name in wanted.items():
        if (namespace, slug) in existing:
            continue
        tag = get_or_create_tag(session, namespace, slug, name=name, commit=False)
        session.add(
            TagLink(
                tag_id=tag.id, target_type=target_type, target_id=target_id, source=source
            )
        )
        added += 1
    for key, link in existing.items():
        if key not in wanted and remove_source(link.source):
            session.delete(link)
            removed += 1
    session.flush()
    return added, removed


def sync_note_tags(
    session: Session, note: JoplinNote, commit: bool = True
) -> Tuple[int, int]:
    """Make the day's note-sourced links match the hashtags in the note body.

    Returns (added, removed)."""
    wanted = {(p.namespace, p.slug): None for p in parse_hashtags(note.body or "")}
    result = _ensure_links(
        session,
        DAY,
        note.title,
        wanted,
        source=SOURCE_NOTE,
        remove_source=lambda s: s == SOURCE_NOTE,
    )
    if commit:
        session.commit()
    return result


def _wanted_from_joplin_titles(titles: Iterable[str]) -> Dict[Tuple[str, str], Optional[str]]:
    # a Joplin tag title is read as a key (`dog:ruffles` names a dog) and kept
    # as the tag's label; one that has nothing slug-shaped in it is skipped
    wanted: Dict[Tuple[str, str], Optional[str]] = {}
    for title in titles:
        try:
            wanted.setdefault(parse_key(title), title)
        except ValueError:
            logger.warning(f"ignoring Joplin tag {title!r}: nothing slug-shaped in it")
    return wanted


def sync_joplin_note_tags(
    session: Session, day: str, titles: Iterable[str], commit: bool = True
) -> Tuple[int, int]:
    """Make a day's joplin-sourced links match the note's tags in Joplin.

    One way: what Joplin has wins for this source, and nothing is written
    back. Returns (added, removed)."""
    result = _ensure_links(
        session,
        DAY,
        day,
        _wanted_from_joplin_titles(titles),
        source=SOURCE_JOPLIN,
        remove_source=lambda s: s == SOURCE_JOPLIN,
    )
    if commit:
        session.commit()
    return result


def sync_joplin_tags_bulk(
    session: Session, titles_by_day: Dict[str, List[str]], commit: bool = True
) -> Tuple[int, int]:
    """Reconcile every day's joplin-sourced links against a full picture of
    Joplin's tags. Days that no longer carry any Joplin tag are cleared too."""
    days_with_links = set(
        session.exec(
            select(TagLink.target_id).where(
                TagLink.target_type == DAY, TagLink.source == SOURCE_JOPLIN
            )
        ).all()
    )
    added = removed = 0
    for day in sorted(set(titles_by_day) | days_with_links):
        a, r = sync_joplin_note_tags(session, day, titles_by_day.get(day, []), commit=False)
        added += a
        removed += r
    if commit:
        session.commit()
    return added, removed


def set_target_tags(
    session: Session,
    target_type: str,
    target_id: str,
    keys: Sequence[str],
    source: str = SOURCE_MANUAL,
    raw_names: bool = False,
    commit: bool = True,
) -> List[Tag]:
    """Replace the non-note links on a target with the given tags.

    `keys` are `namespace:slug` strings, normalised on the way in. With
    `raw_names=True` they are display names instead (as Pocket exported
    them): no namespace is parsed out of them, and the name is kept as the
    tag's label. Only links of the same `source` are removed; a key that
    already has a link of any source is left as it is. Returns every tag now
    on the target."""
    kind_for(target_type)
    wanted: Dict[Tuple[str, str], Optional[str]] = {}
    for key in keys:
        if raw_names:
            parsed, name = ("", slugify_tag(key)), key
        else:
            parsed, name = parse_key(key), None
        wanted.setdefault(parsed, name)
    _ensure_links(
        session,
        target_type,
        str(target_id),
        wanted,
        source=source,
        remove_source=lambda s: s == source,
    )
    if commit:
        session.commit()
    return [tag for tag, _ in tags_for_target(session, target_type, str(target_id))]


# --- reading a tag ----------------------------------------------------------


@dataclass(frozen=True)
class ResolvedRef:
    """What a namespaced tag refers to, when its namespace has a table."""

    kind: str
    id: str
    label: str
    frontend_route: Optional[str] = None


@dataclass(frozen=True)
class TargetRef:
    """One thing a tag is attached to."""

    kind: str
    id: str
    label: str
    source: str
    frontend_route: Optional[str] = None


def resolve_tag(session: Session, tag: Tag) -> Optional[ResolvedRef]:
    kind = ENTITY_KINDS.get(tag.namespace) if tag.namespace else None
    if kind is None or kind.resolve is None:
        return None
    row = kind.resolve(kind, session, tag.slug)
    if row is None:
        return None
    return ResolvedRef(
        kind=kind.key,
        id=kind.id_of(row),
        label=kind.display(row),
        frontend_route=kind.frontend_route,
    )


def tag_targets(session: Session, tag: Tag) -> List[TargetRef]:
    """Everything a tag is attached to, hydrated; kinds in registry order,
    days newest first, everything else by label. Targets whose row is gone
    (or whose type is no longer registered) are skipped."""
    links = session.exec(select(TagLink).where(TagLink.tag_id == tag.id)).all()
    by_kind: Dict[str, List[TargetRef]] = {k: [] for k in ENTITY_KINDS}
    for link in links:
        kind = ENTITY_KINDS.get(link.target_type)
        if kind is None:
            continue
        row = kind.get(kind, session, link.target_id)
        if row is None:
            continue
        by_kind[kind.key].append(
            TargetRef(
                kind=kind.key,
                id=link.target_id,
                label=kind.display(row),
                source=link.source,
                frontend_route=kind.frontend_route,
            )
        )
    out: List[TargetRef] = []
    for key, refs in by_kind.items():
        if key == DAY:
            refs.sort(key=lambda r: r.id, reverse=True)
        else:
            refs.sort(key=lambda r: (r.label.lower(), r.id))
        out.extend(refs)
    return out
