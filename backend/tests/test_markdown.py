from pathlib import Path

import pytest
from mydiary.markdown_edits import MarkdownDoc, MarkdownSection



markdown_text = """
# sync_test_note

## heading

- List item
- List item

## heading 2

```python
## comment
#####=======#######
import antigravity
```

## heading 3

goodbye
"""


def test_markdown_split_and_rejoin():
    md_doc = MarkdownDoc(markdown_text)

    section_existing = md_doc.get_section_by_title("heading")
    assert section_existing is not None

    with pytest.raises(KeyError):
        section_nonexisting = md_doc.get_section_by_title("nonexistent")

    rejoin = "\n".join([section.txt for section in md_doc.sections])
    assert markdown_text == rejoin


def test_update_body(rootdir):
    txt1 = Path(rootdir).joinpath("test_mydiaryday.md").read_text()
    txt2 = Path(rootdir).joinpath("test_mydiaryday2.md").read_text()

    md1 = MarkdownDoc(txt1)
    assert md1.txt == txt1

    md2 = MarkdownDoc(txt2)
    assert md2.txt == txt2

    results = []
    for sec in md1.sections:
        update_txt = md2.get_section_by_title(sec.title).txt
        result = sec.update(update_txt)
        assert result in ["updated", "no update"]
        results.append(result=="updated")
    assert any(results)  # at least one section was updated

    assert md1.txt == txt2


def test_code_block_protects_headings():
    md_doc = MarkdownDoc(markdown_text)
    assert len(md_doc.sections) == 4
    titles = [sec.title for sec in md_doc.sections]
    assert "comment" not in titles  # ## comment inside ``` block must not become a section
    assert "heading 2" in titles    # the section containing the code block is still present


def test_update_force():
    sec = MarkdownSection(["## heading", "", "original line", ""], title="heading")
    result = sec.update("## heading\n\nreplacement\n", force=True)
    assert result == "updated"
    assert sec.content == "replacement"


def test_update_conflict_raises():
    sec = MarkdownSection(["## heading", "", "original line", ""], title="heading")
    with pytest.raises(RuntimeError):
        sec.update("## heading\n\nreplacement\n")


def test_update_no_op_empty_new_content():
    sec = MarkdownSection(["## heading", "", "existing content", ""], title="heading")
    result = sec.update("## heading\n\n\n")
    assert result == "no update"
    assert sec.content == "existing content"


def test_update_no_op_identical():
    txt = "## heading\n\nexisting content\n"
    sec = MarkdownSection(txt.split("\n"), title="heading")
    result = sec.update(txt)
    assert result == "no update"


def test_get_resource_ids():
    sec = MarkdownSection(
        ["## images", "", "![](:/abc123)", "", "![](:/def456)", ""],
        title="images",
    )
    assert sec.get_resource_ids() == ["abc123", "def456"]


def test_set_content_replace():
    sec = MarkdownSection(
        ["## images", "", "![](:/abc123)", "", "![](:/def456)", ""],
        title="images",
    )
    result = sec.set_content("![](:/def456)\n\n![](:/new789)")
    assert result == "updated"
    assert sec.get_resource_ids() == ["def456", "new789"]
    assert sec.lines[0] == "## images"


def test_set_content_empty_populated_section():
    # update() cannot express this (empty new content is a no-op there)
    sec = MarkdownSection(
        ["## images", "", "![](:/abc123)", ""],
        title="images",
    )
    result = sec.set_content("")
    assert result == "updated"
    assert sec.get_resource_ids() == []
    assert sec.content == ""
    assert sec.lines[0] == "## images"


def test_set_content_no_op():
    sec = MarkdownSection(
        ["## images", "", "![](:/abc123)", ""],
        title="images",
    )
    assert sec.set_content("![](:/abc123)") == "no update"


def test_set_content_document_roundtrip():
    body = "\n".join(
        [
            "# title",
            "",
            "## words",
            "",
            "some words",
            "",
            "## images",
            "",
            "![](:/abc123)",
            "",
            "![](:/legacy999)",
            "",
            "## after",
            "",
            "tail content",
        ]
    )
    md_doc = MarkdownDoc(body)
    sec = md_doc.get_section_by_title("images")
    # removal of a subset preserves other refs and the rest of the document
    sec.set_content("![](:/legacy999)")
    assert md_doc.get_image_resource_ids() == ["legacy999"]
    assert "some words" in md_doc.txt
    assert "tail content" in md_doc.txt
    assert "abc123" not in md_doc.txt


def test_ensure_section_returns_an_existing_section():
    md = MarkdownDoc("# Title\n\n## Words\n\nhi\n\n## Images\n\n")
    section = md.ensure_section("Images")
    assert section is md.get_section_by_title("Images")
    assert len(md.sections) == 3


def test_ensure_section_adds_a_missing_section_after_the_named_one():
    md = MarkdownDoc("# Title\n\n## Words\n\nhi\n\n## Images\n\n## Spotify tracks\n\n")
    md.ensure_section("Location", after_title="Images")
    titles = [s.title for s in md.sections if s.title]
    assert titles == ["Words", "Images", "Location", "Spotify tracks"]
    assert "## Location" in md.txt


def test_ensure_section_appends_when_the_anchor_is_absent():
    md = MarkdownDoc("# Title\n\n## Words\n\nhi\n")
    md.ensure_section("Location", after_title="Images")
    assert [s.title for s in md.sections if s.title] == ["Words", "Location"]


def test_ensure_section_is_case_insensitive():
    md = MarkdownDoc("# Title\n\n## Location\n\nexisting\n")
    md.ensure_section("location")
    assert len([s for s in md.sections if s.title.lower() == "location"]) == 1
