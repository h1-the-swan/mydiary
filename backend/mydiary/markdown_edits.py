# -*- coding: utf-8 -*-

DESCRIPTION = """Split Markdown docs into `## ` sections and replace a section's content."""

from collections import OrderedDict
from typing import Any, Generator, List, Tuple


class MarkdownDoc:
    def __init__(
        self,
        txt: str,
        parent: Any = None,
    ) -> None:
        # self.txt = txt
        self.parent = parent

        self.sections = [
            MarkdownSection(sec, title, parent=self, level=2)
            for title, sec in self.split_into_sections(txt, level=2)
        ]

    @property
    def txt(self):
        return "\n".join([section.txt for section in self.sections])

    def __repr__(self) -> str:
        txt_repr = self.txt[:50] + "..." if len(self.txt) > 50 else self.txt
        txt_repr = txt_repr.replace("\n", "\\")
        return f"{self.__class__}({txt_repr})"

    def get_section_by_title(self, title: str) -> "MarkdownSection":
        s = [sec for sec in self.sections if sec.title.lower() == title.lower()]
        if len(s) < 1:
            raise KeyError(f"could not find section with title {title}")
        elif len(s) > 1:
            raise KeyError(f"ERROR: more than one section found with title {title}")
        return s[0]

    def split_into_sections(
        self, markdown_text: str, level=2
    ) -> Generator[Tuple[str, List[str]], None, None]:
        """This is a very simple way of splitting the markdown text into sections.
        It will not handle edge cases very well.

        Args:
            markdown_text (str): full text in Markdown format
            level (int, optional): Heading level to split by. Defaults to 2, meaning "## <Heading label>"

        Yields:
            Generator[Tuple[str, List[str]], None, None]: Tuple of (section title, list of lines)
        """
        heading_indicator = "#" * level
        protect_flag = False
        # sections = OrderedDict()
        this_section = []
        this_section_title = ""
        # this_section_txt = ""
        for line in markdown_text.split("\n"):
            if line.startswith("```"):
                protect_flag = not protect_flag
            if protect_flag is False and line.startswith(heading_indicator + " "):
                # sections.append("\n".join(this_section))
                # sections[this_section_title] = "\n".join(this_section)
                # this_section_txt = "\n".join(this_section)
                yield this_section_title, this_section
                this_section = [line]
                this_section_title = line.strip(heading_indicator).strip()
            else:
                this_section.append(line)
        # sections.append("\n".join(this_section))
        # this_section_txt = "\n".join(this_section)
        yield this_section_title, this_section

    def refresh_all_sections(self):
        for sec in self.sections:
            sec.refresh()


class MarkdownSection:
    def __init__(
        self, lines: List[str], title: str = "", parent: Any = None, level=2
    ) -> None:
        self.lines = lines
        self.title = title
        self.parent = parent
        self.level = level

        self.refresh()

    def refresh(self) -> None:
        self.txt = "\n".join(self.lines)
        self.content = self.get_content()

    def get_content(self) -> str:
        content_lines = self.lines[1:]
        content = "\n".join(content_lines)
        content = content.strip()
        return content

    def __repr__(self) -> str:
        txt_repr = self.txt[:50] + "..." if len(self.txt) > 50 else self.txt
        txt_repr = txt_repr.replace("\n", "\\")
        return f"{self.__class__}({txt_repr})"

    def __str__(self) -> str:
        return self.txt

    def set_content(self, new_content: str) -> str:
        """Replace this section's content unconditionally, preserving the heading line.

        Only for App-owned Sections: see `DiaryNote.edit()` and ADR-0001.
        """
        heading_line = self.lines[0] if self.lines else f"{'#' * self.level} {self.title}"
        new_content = new_content.strip()
        if new_content == self.content:
            return "no update"
        if new_content:
            self.lines = [heading_line, "", *new_content.split("\n"), ""]
        else:
            self.lines = [heading_line, ""]
        self.refresh()
        return "updated"
