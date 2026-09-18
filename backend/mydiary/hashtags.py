# -*- coding: utf-8 -*-

DESCRIPTION = """Find the hashtags in a diary note, and normalise tag names.

A tag is written `#slug` or `#namespace:slug`. The namespace is optional and
says what kind of thing the tag refers to (`#dog:ruffles`), which lets the tag
system resolve it to a real row when a table for that kind exists, and treat
it as a plain grouping string when one does not. Both parts are normalised to
a slug: lowercase ASCII letters, digits, `-` and `_`.

There are two grammars, and the difference is deliberate:

- A *hashtag* in prose is strict. Its slug has to contain a letter, so `#1` and
  `#2024` are not tags, and its namespace has to start with one. It cannot be
  glued to a word, a URL path, an HTML entity or another `#`, so `page#frag`,
  `&#39;` and `## Heading` do not match.
- A *key* -- the `namespace:slug` string the API and UI pass around -- is any
  slug-shaped text. Names imported from elsewhere (the Pocket tags, say) may
  slugify to digits, and they still need to be addressable.

Hashtags are read from the whole note body, and the generated sections of a
note are lists of markdown links, so links, images, autolinks, bare URLs and
code are removed before matching. A `#` inside link text is therefore never a
tag, which is also what the frontend's renderer does.

This module is pure functions over strings -- no database, no network -- so
the grammar can be tested on its own."""

import re
from dataclasses import dataclass
from typing import List, Tuple

from slugify import slugify

# what a slug may contain, as the complement python-slugify replaces
SLUG_DISALLOWED = r"[^-a-z0-9_]+"

HASHTAG_RE = re.compile(
    r"""
    (?<![\w&\#/])                              # not glued to a word, an entity, a heading or a URL path
    \#
    (?:
        (?P<namespace>[^\W\d_][\w-]*):         # namespace, letter-initial, then any slug:
        (?P<nslug>\w[\w-]*)                    # `#issue:42` and `#day:2026-09-13` are unambiguous
      |
        (?P<slug>(?=[\w-]*[^\W\d_])\w[\w-]*)   # bare slug: word-initial and contains a letter,
    )                                          # so `#1` and `#2024` are not tags
    (?![\w:])                                  # a second colon or more word breaks the match
    """,
    re.VERBOSE,
)

# markdown that is never prose, removed before matching (order matters: fences
# first, so a link inside a code block does not survive as text)
_FENCED_CODE = re.compile(r"^(`{3,}|~{3,})[^\n]*\n.*?(?:^\1[^\n]*$|\Z)", re.M | re.S)
_INLINE_CODE = re.compile(r"`[^`\n]+`")
_LINK_OR_IMAGE = re.compile(r"!?\[[^\]]*\]\([^)]*\)")
_AUTOLINK = re.compile(r"<[a-zA-Z][a-zA-Z0-9+.-]*:[^>\s]*>")
_BARE_URL = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.-]*://\S+|\bwww\.\S+")


@dataclass(frozen=True)
class ParsedTag:
    namespace: str  # "" when the tag has none
    slug: str
    raw: str  # the text after the `#`, as written

    @property
    def key(self) -> str:
        return tag_key(self.namespace, self.slug)


def slugify_tag(text: str) -> str:
    """Normalise free text to a tag slug.

    Raises ValueError when nothing slug-shaped is left, which is how callers
    learn that "!!!" is not a tag rather than getting an empty key."""
    slug = slugify(text or "", regex_pattern=SLUG_DISALLOWED).strip("-_")
    if not slug:
        raise ValueError(f"nothing slug-shaped in {text!r}")
    return slug


def tag_key(namespace: str, slug: str) -> str:
    """The canonical `namespace:slug` (or bare `slug`) string for a tag."""
    return f"{namespace}:{slug}" if namespace else slug


def parse_key(key: str) -> Tuple[str, str]:
    """Split a key into `(namespace, slug)`, normalising both halves.

    Only the first colon separates the namespace; anything after it belongs to
    the slug. A leading `#` is tolerated so a pasted hashtag works as a key."""
    key = (key or "").strip().lstrip("#")
    namespace, sep, rest = key.partition(":")
    if not sep:
        return "", slugify_tag(key)
    try:
        namespace = slugify_tag(namespace)
    except ValueError:
        namespace = ""
    return namespace, slugify_tag(rest)


def strip_non_prose(markdown: str) -> str:
    """Remove the parts of a markdown document a hashtag may not live in."""
    text = _FENCED_CODE.sub(" ", markdown)
    text = _INLINE_CODE.sub(" ", text)
    text = _LINK_OR_IMAGE.sub(" ", text)
    text = _AUTOLINK.sub(" ", text)
    text = _BARE_URL.sub(" ", text)
    return text


def parse_hashtags(markdown: str) -> List[ParsedTag]:
    """Every distinct hashtag in a document, in order of first appearance."""
    found: List[ParsedTag] = []
    seen = set()
    for m in HASHTAG_RE.finditer(strip_non_prose(markdown or "")):
        try:
            slug = slugify_tag(m.group("nslug") or m.group("slug"))
            namespace = slugify_tag(m.group("namespace")) if m.group("namespace") else ""
        except ValueError:
            # a slug that is letters to the regex but nothing after
            # transliteration; not a tag we can name
            continue
        if (namespace, slug) in seen:
            continue
        seen.add((namespace, slug))
        found.append(ParsedTag(namespace=namespace, slug=slug, raw=m.group(0)[1:]))
    return found
