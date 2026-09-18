# -*- coding: utf-8 -*-

import pytest

from mydiary.hashtags import ParsedTag, parse_hashtags, parse_key, slugify_tag, tag_key


def keys(text):
    return [tag_key(t.namespace, t.slug) for t in parse_hashtags(text)]


class TestSlugify:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("saved for later", "saved-for-later"),
            ("a.v. club", "a-v-club"),
            ("https://savage.love", "https-savage-love"),
            ("Ruffles", "ruffles"),
            ("new_york", "new_york"),
            ("  -foo_ ", "foo"),
            ("2024", "2024"),
            ("café", "cafe"),
        ],
    )
    def test_shapes(self, raw, expected):
        assert slugify_tag(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "!!!", "--_"])
    def test_nothing_left_is_an_error(self, raw):
        with pytest.raises(ValueError):
            slugify_tag(raw)


class TestKeys:
    def test_tag_key_with_and_without_namespace(self):
        assert tag_key("dog", "ruffles") == "dog:ruffles"
        assert tag_key("", "hiking") == "hiking"

    @pytest.mark.parametrize(
        "key,expected",
        [
            ("dog:ruffles", ("dog", "ruffles")),
            ("Dog:Ruffles", ("dog", "ruffles")),
            ("Hiking", ("", "hiking")),
            # only the first colon separates the namespace
            ("re:read:more", ("re", "read-more")),
            # an empty namespace half is a bare tag
            (":foo", ("", "foo")),
            ("saved for later", ("", "saved-for-later")),
        ],
    )
    def test_parse_key(self, key, expected):
        assert parse_key(key) == expected

    def test_parse_key_round_trip(self):
        for ns, slug in [("dog", "ruffles"), ("", "hiking"), ("book", "the-husbands")]:
            assert parse_key(tag_key(ns, slug)) == (ns, slug)

    @pytest.mark.parametrize("key", ["", ":", "dog:", "!!!"])
    def test_parse_key_rejects_empty_slug(self, key):
        with pytest.raises(ValueError):
            parse_key(key)


class TestParseHashtags:
    def test_namespaced(self):
        assert parse_hashtags("Walked #dog:Ruffles today") == [
            ParsedTag(namespace="dog", slug="ruffles", raw="dog:Ruffles")
        ]

    def test_bare(self):
        assert parse_hashtags("went #hiking") == [
            ParsedTag(namespace="", slug="hiking", raw="hiking")
        ]

    def test_case_insensitive_and_deduped_in_order(self):
        assert keys("#b #B #a #dog:X #Dog:x") == ["b", "a", "dog:x"]

    def test_underscores_and_hyphens_survive(self):
        assert keys("#new_york #well-being #book:the-husbands") == [
            "new_york",
            "well-being",
            "book:the-husbands",
        ]

    def test_trailing_punctuation_is_not_part_of_the_tag(self):
        assert keys("(#hiking) #hiking. #hiking, #foo-") == ["hiking", "foo"]

    def test_bare_slug_needs_a_letter(self):
        assert keys("#h3 ok, #1 no, #2024 no") == ["h3"]

    def test_namespaced_slug_may_be_all_digits(self):
        # `#1` is ambiguous in prose; `#day:2026-09-13` and `#issue:42` are not
        assert keys("see #day:2026-09-13 and #issue:42") == ["day:2026-09-13", "issue:42"]

    def test_namespace_without_slug_is_nothing(self):
        assert keys("see #dog: he was cute") == []

    def test_second_colon_breaks_the_match(self):
        assert keys("#dog:ruffles:extra") == []

    def test_leading_hyphen_is_nothing(self):
        assert keys("#-bad") == []

    def test_headings_are_not_tags(self):
        assert keys("# Sep 13, 2026\n\n## Words\n\n### Sub\n") == []

    def test_url_fragments_are_not_tags(self):
        assert keys("see http://x.com/#frag and http://x.com/page#frag") == []

    def test_html_entities_are_not_tags(self):
        assert keys("it&#39;s fine &#x27;") == []

    def test_link_text_is_skipped_with_the_link(self):
        assert keys("[Louis and the #MeToo movement](http://example.com) #real") == [
            "real"
        ]

    def test_pocket_style_link_list_yields_nothing(self):
        body = "\n".join(
            [
                "## Pocket articles",
                "",
                "- [Why #1 matters](https://example.com/a#top)",
                "- [The #MeToo reckoning](https://example.com/b)",
                "",
                "## Spotify tracks",
                "",
                "- [Track #7 #rock](spotify:track:abc)",
            ]
        )
        assert keys(body) == []

    def test_images_and_autolinks_are_skipped(self):
        assert keys("![img](:/abc#x) <http://ex.com/#frag> #photo") == ["photo"]

    def test_code_is_skipped(self):
        body = "\n".join(
            [
                "```python",
                "x = '#not-a-tag'",
                "```",
                "inline `#alsonot` but #yes",
            ]
        )
        assert keys(body) == ["yes"]

    def test_unicode_is_slugified(self):
        assert keys("#café") == ["cafe"]

    def test_empty(self):
        assert parse_hashtags("") == []
