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
