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

from defusedxml import minidom
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
                elem.setAttribute("w14:textId", _generate_hex_id())

        def add_rsid_to_r(elem):
            # Use w:rsidDel for <w:r> inside <w:del>, otherwise w:rsidR
            if is_inside_deletion(elem):
                if not elem.hasAttribute("w:rsidDel"):
                    elem.setAttribute("w:rsidDel", self.rsid)
            else:
                if not elem.hasAttribute("w:rsidR"):
                    elem.setAttribute("w:rsidR", self.rsid)

        def add_tracked_change_attrs(elem):
            # Auto-assign w:id if not present
            if not elem.hasAttribute("w:id"):
                elem.setAttribute("w:id", str(self._get_next_change_id()))
            if not elem.hasAttribute("w:author"):
                elem.setAttribute("w:author", self.author)
            if not elem.hasAttribute("w:date"):
                elem.setAttribute("w:date", timestamp)
            # Add w16du:dateUtc for tracked changes (same as w:date since we generate UTC timestamps)
            if elem.tagName in ("w:ins", "w:del") and not elem.hasAttribute(
                "w16du:dateUtc"
            ):
                self._ensure_w16du_namespace()
                elem.setAttribute("w16du:dateUtc", timestamp)

        def add_comment_attrs(elem):
            if not elem.hasAttribute("w:author"):
                elem.setAttribute("w:author", self.author)
            if not elem.hasAttribute("w:date"):
                elem.setAttribute("w:date", timestamp)
            if not elem.hasAttribute("w:initials"):
                elem.setAttribute("w:initials", self.initials)

        def add_comment_extensible_date(elem):
            # Add w16cex:dateUtc for comment extensible elements
            if not elem.hasAttribute("w16cex:dateUtc"):
                self._ensure_w16cex_namespace()
                elem.setAttribute("w16cex:dateUtc", timestamp)

        def add_xml_space_to_t(elem):
            # Add xml:space="preserve" to w:t if text has leading/trailing whitespace
            if (
                elem.firstChild
                and elem.firstChild.nodeType == elem.firstChild.TEXT_NODE
            ):
                text = elem.firstChild.data
                if text and (text[0].isspace() or text[-1].isspace()):
                    if not elem.hasAttribute("xml:space"):
                        elem.setAttribute("xml:space", "preserve")

        for node in nodes:
            if node.nodeType != node.ELEMENT_NODE:
                continue

            # Handle the node itself
            if node.tagName == "w:p":
                add_rsid_to_p(node)
            elif node.tagName == "w:r":
                add_rsid_to_r(node)
            elif node.tagName == "w:t":
                add_xml_space_to_t(node)
            elif node.tagName in ("w:ins", "w:del"):
                add_tracked_change_attrs(node)
            elif node.tagName == "w:comment":
                add_comment_attrs(node)
            elif node.tagName == "w16cex:commentExtensible":
                add_comment_extensible_date(node)

            # Process descendants (getElementsByTagName doesn't return the element itself)
            for elem in node.getElementsByTagName("w:p"):
                add_rsid_to_p(elem)
            for elem in node.getElementsByTagName("w:r"):
                add_rsid_to_r(elem)
            for elem in node.getElementsByTagName("w:t"):
                add_xml_space_to_t(elem)
            for tag in ("w:ins", "w:del"):
                for elem in node.getElementsByTagName(tag):
                    add_tracked_change_attrs(elem)
            for elem in node.getElementsByTagName("w:comment"):
                add_comment_attrs(elem)
            for elem in node.getElementsByTagName("w16cex:commentExtensible"):
                add_comment_extensible_date(elem)

    def replace_node(self, elem, new_content):
        """Replace node with automatic attribute injection."""
        nodes = super().replace_node(elem, new_content)
        self._inject_attributes_to_nodes(nodes)
        return nodes

    def insert_after(self, elem, xml_content):
        """Insert after with automatic attribute injection."""
        nodes = super().insert_after(elem, xml_content)
        self._inject_attributes_to_nodes(nodes)
        return nodes

    def insert_before(self, elem, xml_content):
        """Insert before with automatic attribute injection."""
        nodes = super().insert_before(elem, xml_content)
        self._inject_attributes_to_nodes(nodes)
        return nodes

    def append_to(self, elem, xml_content):
        """Append to with automatic attribute injection."""
        nodes = super().append_to(elem, xml_content)
        self._inject_attributes_to_nodes(nodes)
        return nodes

    def revert_insertion(self, elem):
        """Reject an insertion by wrapping its content in a deletion.

        Wraps all runs inside w:ins in w:del, converting w:t to w:delText.
        Can process a single w:ins element or a container element with multiple w:ins.

        Args:
            elem: Element to process (w:ins, w:p, w:body, etc.)

        Returns:
            list: List containing the processed element(s)

        Raises:
            ValueError: If the element contains no w:ins elements

        Example:
            # Reject a single insertion
            ins = doc["word/document.xml"].get_node(tag="w:ins", attrs={"w:id": "5"})
            doc["word/document.xml"].revert_insertion(ins)

            # Reject all insertions in a paragraph
            para = doc["word/document.xml"].get_node(tag="w:p", line_number=42)
            doc["word/document.xml"].revert_insertion(para)
        """
        # Collect insertions
        ins_elements = []
        if elem.tagName == "w:ins":
            ins_elements.append(elem)
        else:
            ins_elements.extend(elem.getElementsByTagName("w:ins"))

        # Validate that there are insertions to reject
        if not ins_elements:
            raise ValueError(
                f"revert_insertion requires w:ins elements. "
                f"The provided element <{elem.tagName}> contains no insertions. "
            )

        # Process all insertions - wrap all children in w:del
        for ins_elem in ins_elements:
            runs = list(ins_elem.getElementsByTagName("w:r"))
            if not runs:
                continue

            # Create deletion wrapper
            del_wrapper = self.dom.createElement("w:del")

            # Process each run
            for run in runs:
                # Convert w:t → w:delText and w:rsidR → w:rsidDel
                if run.hasAttribute("w:rsidR"):
                    run.setAttribute("w:rsidDel", run.getAttribute("w:rsidR"))
                    run.removeAttribute("w:rsidR")
                elif not run.hasAttribute("w:rsidDel"):
                    run.setAttribute("w:rsidDel", self.rsid)

                for t_elem in list(run.getElementsByTagName("w:t")):
                    del_text = self.dom.createElement("w:delText")
                    # Copy ALL child nodes (not just firstChild) to handle entities
                    while t_elem.firstChild:
                        del_text.appendChild(t_elem.firstChild)
                    for i in range(t_elem.attributes.length):
                        attr = t_elem.attributes.item(i)
                        del_text.setAttribute(attr.name, attr.value)
                    t_elem.parentNode.replaceChild(del_text, t_elem)

            # Move all children from ins to del wrapper
            while ins_elem.firstChild:
                del_wrapper.appendChild(ins_elem.firstChild)

            # Add del wrapper back to ins
            ins_elem.appendChild(del_wrapper)

            # Inject attributes to the deletion wrapper
            self._inject_attributes_to_nodes([