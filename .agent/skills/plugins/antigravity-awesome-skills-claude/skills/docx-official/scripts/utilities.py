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
from typing import Optional,