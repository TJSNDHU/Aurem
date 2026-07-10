#!/usr/bin/env python3
"""
Library for working with Word documents: comments, tracked changes, and editing.

Usage:
    from skills.docx.scripts.document import Document

    # Initialize
    doc = Document('workspace/unpacked')
    doc = Document('workspace/unpacked', author="John Doe", initials="JD")

    # Find nodes
    node = doc["word/document.xml"].get_node(tag="w:del", attrs={"w:id": "1"})
    node = doc["word/document.xml"].get_node(tag="w:p", line_number=10)

    # Add comments
    doc.add_comment(start=node, end=node, text="Comment text")
    doc.reply_to_comment(parent_comment_id=0, text="Reply text")

    # Suggest tracked changes
    doc["word/document.xml"].suggest_deletion(node)  # Delete content
    doc["word/document.xml"].revert_insertion(ins_node)  # Reject insertion
    doc["word/document.xml"].revert_deletion(del_node)  # Reject deletion

    # Save
    doc.save()
"""

import html
import random
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from defusedxml import minidom as defusedxml_minidom
from ooxml.scripts.pack import pack_document
from ooxml.scripts.validation.docx import DOCXSchemaValidator
from ooxml.scripts.validation.redlining import RedliningValidator

from .utilities import XMLEditor

# Path to template files
TEMPLATE_DIR = Path(__file__).parent / "templates"


class DocxXMLEditor(XMLEditor):
    """XMLEditor that automatically applies RSID, author, and date to new elements.

    Automatically adds attributes to elements that support them when inserting new content:
    - w:rsidR, w:rsidRDefault, w:rsidP (for w:p and w:r elements)
    - w:author and w:date (for w:ins, w:del, w:comment elements)
    - w:id (for w:ins and w:del elements)

    Attributes:
        dom (defusedxml.minidom.Document): The DOM document for direct manipulation
    """

    def __init__(
        self, xml_path, rsid: str, author: str = "Claude", initials: str = "C"
    ):
        """Initialize with required RSID and optional author.

        Args:
            xml_path: Path to XML file to edit
            rsid: RSID to automatically apply to new elements
            author: Author name for tracked changes and comments (default: "Claude")
            initials: Author initials (default: "C")
        """
        super().__init__(xml_path)
        self.rsid = rsid
        self.author = author
        self.initials = initials

    def _get_next_change_id(self):
        """Get the next available change ID by checking all tracked change elements."""
        max_id = -1
        for tag in ("w:ins", "w:del"):
            elements = self.dom.getElementsByTagName(tag)
            for elem in elements:
                change_id = elem.getAttribute("w:id")
                if change_id:
                    try:
                        max_id = max(max_id, int(change_id))
                    except ValueError:
                        pass
        return max_id + 1

    def _ensure_w16du_namespace(self):
        """Ensure w16du namespace is declared on the root element."""
        root = self.dom.documentElement
        if not root.hasAttribute("xmlns:w16du"):  # type: ignore
            root.setAttribute(  # type: ignore
                "xmlns:w16du",
                "http://schemas.microsoft.com/office/word/2023/wordml/word16du",
            )

    def _ensure_w16cex_namespace(self):
        """Ensure w16cex namespace is declared on the root element."""
        root = self.dom.documentElement
        if not root.hasAttribute("xmlns:w16cex"):  # type: ignore
            root.setAttribute(  # type: ignore
                "xmlns:w16cex",
                "http://schemas.microsoft.com/office/word/2018/wordml/cex",
            )

    def _ensure_w14_namespace(self):
        """Ensure w14 namespace is declared on the root element."""
        root = self.dom.documentElement
        if not root.hasAttribute("xmlns:w14"):  # type: ignore
            root.setAttribute(  # type: ignore
                "xmlns:w14",
                "http://schemas.microsoft.com/office/word/2010/wordml",
            )

    def _inject_attributes_to_nodes(self, nodes):
        """Inject RSID, author, and date attributes into DOM nodes where applicable.

        Adds attributes to elements that support them:
        - w:r: gets w:rsidR (or w:rsidDel if inside w:del)
        - w:p: gets w:rsidR, w:rsidRDefault, w:rsidP, w14:paraId, w14:textId
        - w:t: gets xml:space="preserve" if text has leading/trailing whitespace
        - w:ins, w:del: get w:id, w:author, w:date, w16du:dateUtc
        - w:comment: gets w:author, w:date, w:initials
        - w16cex:commentExtensible: gets w16cex:dateUtc

        Args:
            nodes: List of DOM nodes to process
        """
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        def is_inside_deletion(elem):
            """Check if element is inside a w:del element."""
            parent = elem.parentNode
            while parent:
                if parent.nodeType == parent.ELEMENT_NODE and parent.tagName == "w:del":
                    return True
                parent = parent.parentNode
            return False

        def add_rsid_to_p(elem):
            if not elem.hasAttribute("w:rsidR"):
                elem.setAttribute("w:rsidR", self.rsid)
            if not elem.hasAttribute("w:rsidRDefault"):
                elem.setAttribute("w:rsidRDefault", self.rsid)
            if not elem.hasAttribute("w:rsidP"):
                elem.setAttribute("w:rsidP", self.rsid)
            # Add w14:paraId and w14:textId if not present
            if not elem.hasAttribute("w14:paraId"):
                self._ensure_w14_namespace()
                elem.setAttribute("w14:paraId", _generate_hex_id())
            if not elem.hasAttribute("w14:textId"):
                self._ensure_w14_namespace()
                elem.setAttribute