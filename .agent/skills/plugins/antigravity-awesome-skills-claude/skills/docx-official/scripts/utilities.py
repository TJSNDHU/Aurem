#!/usr/bin/env python3
"""
Utilities for editing OOXML documents.

This module provides XMLEditor, a tool for manipulating XML files with support for
line-number-based node finding and DOM manipulation. Each element is automatically
annotated with its original line and column position during parsing.

Example usage:
    editor = XMLEditor("document.xml")

    # Find node by line number or range
    elem = editor.get_node(tag="w:r", line_number=519)
    elem = editor.get_node(tag="w:p", line_number=range(100, 200))

    # Find node by text content
    elem = editor.get_node(tag="w:p", contains="specific text")

    # Find node by attributes
    elem = editor.get_node(tag="w:r", attrs={"w:id": "target"})

    # Combine filters
    elem = editor.get_node(tag="w:p", line_number=range(1, 50), contains="text")

    # Replace, insert, or manipulate
    new_elem = editor.replace_node(elem, "<w:r><w:t>new text</w:t></w:r>")
    editor.insert_after(new_elem, "<w:r><w:t>more</w:t></w:r>")

    # Save changes
    editor.save()
"""

import html
from pathlib import Path
from typing import Optional, Union

import defusedxml.minidom
import defusedxml.sax


class XMLEditor:
    """
    Editor for manipulating OOXML XML files with line-number-based node finding.

    This class parses XML files and tracks the original line and column position
    of each element. This enables finding nodes by their line number in the original
    file, which is useful when working with Read tool output.

    Attributes:
        xml_path: Path to the XML file being edited
        encoding: Detected encoding of the XML file ('ascii' or 'utf-8')
        dom: Parsed DOM tree with parse_position attributes on elements
    """

    def __init__(self, xml_path):
        """
        Initialize with path to XML file and parse with line number tracking.

        Args:
            xml_path: Path to XML file to edit (str or Path)

        Raises:
            ValueError: If the XML file does not exist
        """
        self.xml_path = Path(xml_path)
        if not self.xml_path.exists():
            raise ValueError(f"XML file not found: {xml_path}")

        with open(self.xml_path, "rb") as f:
            header = f.read(200).decode("utf-8", errors="ignore")
        self.encoding = "ascii" if 'encoding="ascii"' in header else "utf-8"

        parser = _create_line_tracking_parser()
        self.dom = defusedxml.minidom.parse(str(self.xml_path), parser)

    def get_node(
        self,
        tag: str,
        attrs: Optional[dict[str, str]] = None,
        line_number: Optional[Union[int, range]] = None,
        contains: Optional[str] = None,
    ):
        """
        Get a DOM element by tag and identifier.

        Finds an element by either its line number in the original file or by
        matching attribute values. Exactly one match must be found.

        Args:
            tag: The XML tag name (e.g., "w:del", "w:ins", "w:r")
            attrs: Dictionary of attribute name-value pairs to match (e.g., {"w:id": "1"})
            line_number: Line number (int) or line range (range) in original XML file (1-indexed)
            contains: Text string that must appear in any text node within the element.
                      Supports both entity notation (&#8220;) and Unicode characters (\u201c).

        Returns:
            defusedxml.minidom.Element: The matching DOM element

        Raises:
            ValueError: If node not found or multiple matches found

        Example:
            elem = editor.get_node(tag="w:r", line_number=519)
            elem = editor.get_node(tag="w:r", line_number=range(100, 200))
            elem = editor.get_node(tag="w:del", attrs={"w:id": "1"})
            elem = editor.get_node(tag="w:p", attrs={"w14:paraId": "12345678"})
            elem = editor.get_node(tag="w:commentRangeStart", attrs={"w:id": "0"})
            elem = editor.get_node(tag="w:p", contains="specific text")
            elem = editor.get_node(tag="w:t", contains="&#8220;Agreement")  # Entity notation
            elem = editor.get_node(tag="w:t", contains="\u201cAgreement")   # Unicode character
        """
        matches = self._find_matching_elements(tag, attrs, line_number, contains)
        self._validate_matches(matches, tag, attrs, line_number, contains)
        return matches[0]

    def _find_matching_elements(self, tag, attrs, line_number, contains):
        """Find all elements matching the given filters."""
        matches = []
        for elem in self.dom.getElementsByTagName(tag):
            if self._element_matches_filters(elem, attrs, line_number, contains):
                matches.append(elem)
        return matches

    def _element_matches_filters(self, elem, attrs, line_number, contains):
        """Check if an element matches all specified filters."""
        if not self._matches_line_number(elem, line_number):
            return False
        if not self._matches_attrs(elem, attrs):
            return False
        if not self._matches_contains(elem, contains):
            return False
        return True

    def _matches_line_number(self, elem, line_number):
        """Check if element matches line number filter."""
        if line_number is None:
            return True
        parse_pos = getattr(elem, "parse_position", (None,))
        elem_line = parse_pos[0]
        if isinstance(line_number, range):
            return elem_line in line_number
        return elem_line == line_number

    def _matches_attrs(self, elem, attrs):
        """Check if element matches attribute filter."""
        if attrs is None:
            return True
        return all(
            elem.getAttribute(attr_name) == attr_value
            for attr_name, attr_value in attrs.items()
        )

    def _matches_contains(self, elem, contains):
        """Check if element matches text content filter."""
        if contains is None:
            return True
        elem_text = self._get_element_text(elem)
        normalized_contains = html.unescape(contains)
        return normalized_contains in elem_text

    def _validate_matches(self, matches, tag, attrs, line_number, contains):
        """Validate that exactly one match was found, raise error otherwise."""
        if not matches:
            self._raise_not_found_error(tag, attrs, line_number, contains)
        if len(matches) > 1:
            raise ValueError(
                f"Multiple nodes found: <{tag}>. "
                f"Add more filters (attrs, line_number, or contains) to narrow the search."
            )

    def _raise_not_found_error(self, tag, attrs, line_number, contains):
        """Raise a descriptive error when no matches are found."""
        filters = self._build_filter_description(attrs, line_number, contains)
        filter_desc = " ".join(filters) if filters else ""
        base_msg = f"Node not found: <{tag}> {filter_desc}".strip()
        hint = self._get_search_hint(contains, line_number, attrs)
        raise ValueError(f"{base_msg}. {hint}")

    def _build_filter_description(self, attrs, line_number, contains):
        """Build a human-readable description of active filters."""
        filters = []
        if line_number is not None:
            line_str = (
                f"lines {line_number.start}-{line_number.stop - 1}"
                if isinstance(line_number, range)
                else f"line {line_number}"
            )
            filters.append(f"at {line_str}")
        if attrs is not None:
            filters.append(f"with attributes {attrs}")
        if contains is not None:
            filters.append(f"containing '{contains}'")
        return filters

    def _get_search_hint(self, contains, line_number, attrs):
        """Get a helpful hint based on which filters were used."""
        if contains:
            return "Text may be split across elements or use different wording."
        if line_number:
            return "Line numbers may have changed if document was modified."
        if attrs:
            return "Verify attribute values are correct."
        return "Try adding filters (attrs, line_number, or contains)."

    def _get_element_text(self, elem):
        """
        Recursively extract all text content from an element.

        Skips text nodes that contain only whitespace (spaces, tabs, newlines),
        which typically represent XML formatting rather than document content.

        Args:
            elem: defusedxml.minidom.Element to extract text from

        Returns:
            str: Concatenated text from all non-whitespace text nodes within the element
        """
        text_parts = []
        for node in elem.childNodes:
            if node.nodeType == node.TEXT_NODE:
                # Skip whitespace-only text nodes (XML formatting)
                if node.data.strip():
                    text_parts.append(node.data)
            elif node.nodeType == node.ELEMENT_NODE:
                text_parts.append(self._get_element_text(node))
        return "".join(text_parts)

    def replace_node(self, elem, new_content):
        """
        Replace a DOM element with new XML content.

        Args:
            elem: defusedxml.minidom.Element to replace
            new_content: String containing XML to replace the node with

        Returns:
            List[defusedxml.minidom.Node]: All inserted nodes

        Example:
            new_nodes = editor.replace_node(old_elem, "<w:r><w:t>text</w:t></w:r>")
        """
        parent = elem.parentNode
        nodes = self._parse_fragment(new_content)
        for node in nodes:
            parent.insertBefore(node, elem)
        parent.removeChild(elem)
        return nodes

    def insert_after(self, elem, xml_content):
        """
        Insert XML content after a DOM element.

        Args:
            elem: defusedxml.minidom.Element to insert after
            xml_content: String containing XML to insert

        Returns:
            List[defusedxml.minidom.Node]: All inserted nodes

        Example:
            new_nodes = editor.insert_after(elem, "<w:r><w:t>text</w:t></w:r>")
        """
        parent = elem.parentNode
        next_sibling = elem.nextSibling
        nodes = self._parse_fragment(xml_content)
        for node in nodes:
            if next_sibling:
                parent.insertBefore(node, next_sibling)
            else:
                parent.appendChild(node)
        return nodes

    def insert_before(self, elem, xml_content):
        """
        Insert XML content before a DOM element.

        Args:
            elem: defusedxml.minidom.Element to insert before
            xml_content: String containing XML to insert

        Returns:
            List[defusedxml.minidom.Node]: All inserted nodes

        Example:
            new_nodes = editor.insert_before(elem, "<w:r><w:t>text</w:t></w:r>")
        """
        parent = elem.parentNode
        nodes = self._parse_fragment(xml_content)
        for node in nodes:
            parent.insertBefore(node, elem)
        return nodes

    def append_to(self, elem, xml_content):
        """
        Append XML content as a child of a DOM element.

        Args:
            elem: defusedxml.minidom.Element to append to
            xml_content: String containing XML to append

        Returns:
            List[defusedxml.minidom.Node]: All inserted nodes

        Example:
            new_nodes = editor.append_to(elem, "<w:r><w:t>text</w:t></w:r>")
        """
        nodes = self._parse_fragment(xml_content)
        for node in nodes:
            elem.appendChild(node)
        return nodes

    def get_next_rid(self):
        """Get the next available rId for relationships files."""
        max_id = 0
        for rel_elem in self.dom.getElementsByTagName("Relationship"):
            rel_id = rel_elem.getAttribute("Id")
            if rel_id.startswith("rId"):
                try:
                    max_id = max(max_id, int(rel_id[3:]))
                except ValueError:
                    pass
        return f"rId{max_id + 1}"

    def save(self):
        """
        Save the edited XML back to the file.

        Serializes the DOM tree and writes it back to the original file path,
        preserving the original encoding (ascii or utf-8).
        """
        content = self.dom.toxml(encoding=self.encoding)
        self.xml_path.write_bytes(content)

    def _parse_fragment(self, xml_content):
        """
        Parse XML fragment and return list of imported nodes.

        Args:
            xml_content: String containing XML fragment

        Returns:
            List of defusedxml.minidom.Node objects imported into this document

        Raises:
            AssertionError: If fragment contains no element nodes
        """
        # Extract namespace declarations from the root document element
        root_elem = self.dom.documentElement
        namespaces = []
        if root_elem and root_elem.attributes:
            for i in range(root_elem.attributes