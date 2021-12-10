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
    rejoin = "\n".join([section.txt for section in md_doc.sections])
    assert markdown_text == rejoin