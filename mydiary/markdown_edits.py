# -*- coding: utf-8 -*-

DESCRIPTION = """Make edits to Markdown docs, prioritizing making sure nothing is lost from original."""

from typing import Any, List

import logging

root_logger = logging.getLogger()
logger = root_logger.getChild(__name__)


class MarkdownDoc:
    def __init__(
        self,
        txt: str,
        parent: Any = None,
    ) -> None:
        self.txt = txt
        self.parent = parent

        self.sections = [
            MarkdownSection(sec, parent=self, level=2)
            for sec in self.split_into_sections(self.txt, level=2)
        ]

    def __repr__(self) -> str:
        txt_repr = self.txt[:50] + "..." if len(self.txt) > 50 else self.txt
        txt_repr = txt_repr.replace("\n", "\\")
        return f'{self.__class__}({txt_repr})'

    def split_into_sections(self, markdown_text: str, level=2) -> List[str]:
        """This is a very simple way of splitting the markdown text into sections.
        It will not handle edge cases very well.

        Args:
            markdown_text (str): full text in Markdown format
            level (int, optional): Heading level to split by. Defaults to 2, meaning "## <Heading label>"

        Returns:
            List[str]: list of original text split into sections (with e.g. "## " removed)
        """        
        heading_indicator = "#" * level
        return markdown_text.split(f"\n{heading_indicator} ")


class MarkdownSection:
    def __init__(self, txt: str, parent: Any = None, level=2) -> None:
        self.txt = txt
        self.parent = parent
        self.level = level

    def __repr__(self) -> str:
        txt_repr = self.txt[:50] + "..." if len(self.txt) > 50 else self.txt
        txt_repr = txt_repr.replace("\n", "\\")
        return f'{self.__class__}({txt_repr})'
