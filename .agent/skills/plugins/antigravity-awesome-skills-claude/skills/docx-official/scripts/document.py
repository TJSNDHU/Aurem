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
    node = doc["word/document.xml"].get_node(tag="w:p", line_number=10