"""
Base validator with common validation logic for document files.
"""

import re
from pathlib import Path

import lxml.etree


class BaseSchemaValidator:
    """Base validator with common validation logic for document files."""

    # Elements whose 'id' attributes must be unique within their file
    # Format: element_name -> (attribute_name, scope)
    # scope can be 'file' (unique within file) or 'global' (unique across all files)
    UNIQUE_ID_REQUIREMENTS = {
        # Word elements
        "comment": ("id", "file"),  # Comment IDs in comments.xml
        "commentrangestart": ("id", "file"),  # Must match comment IDs
        "commentrangeend": ("id", "file"),  # Must match comment IDs
        "bookmarkstart": ("id", "file"),  # Bookmark start IDs
        "bookmarkend": ("id", "file"),  # Bookmark end IDs
        # Note: ins and del (track changes) can share IDs when part of same revision
        # PowerPoint elements
        "sldid": ("id", "file"),  # Slide IDs in presentation.xml
        "sldmasterid": ("id", "global"),  # Slide master IDs must be globally unique
        "sldlayoutid": ("id", "global"),  # Slide layout IDs must be globally unique
        "cm": ("authorid", "file"),  # Comment author IDs
        # Excel elements
        "sheet": ("sheetid", "file"),  # Sheet IDs in workbook.xml
        "definedname": ("id", "file"),  # Named range IDs
        # Drawing/Shape elements (all formats)
        "cxnsp": ("id", "file"),  # Connection shape IDs
        "sp": ("id", "file"),  # Shape IDs
        "pic": ("id", "file"),  # Picture IDs
        "grpsp": ("id", "file"),  # Group shape IDs
    }

    # Mapping of element names to expected relationship types
    # Subclasses should override this with format-specific mappings
    ELEMENT_RELATIONSHIP_TYPES = {}

    # Unified schema mappings for all Office document types
    SCHEMA_MAPPINGS = {
        # Document type specific schemas
        "word": "ISO-IEC29500-4_2016/wml.xsd",  # Word documents
        "ppt": "ISO-IEC29500-4_2016/pml.xsd",  # PowerPoint presentations
        "xl": "ISO-IEC29500-4_2016/sml.xsd",  # Excel spreadsheets
        # Common file types
        "[Content_Types].xml": "ecma/fouth-edition/opc-contentTypes.xsd",
        "app.xml": "ISO-IEC29500-4_2016/shared-documentPropertiesExtended.xsd",
        "core.xml": "ecma/fouth-edition/opc-coreProperties.xsd",
        "custom.xml": "ISO-IEC29500-4_2016/shared-documentPropertiesCustom.xsd",
        ".rels": "ecma/fouth-edition/opc-relationships.xsd",
        # Word-specific files
        "people.xml": "microsoft/wml-2012.xsd",
        "commentsIds.xml": "microsoft/wml-cid-2016.xsd",
        "commentsExtensible.xml": "microsoft/wml-cex-2018.xsd",
        "commentsExtended.xml": "microsoft/wml-2012.xsd",
        # Chart files (common across document types)
        "chart": "ISO-IEC29500-4_2016/dml-chart.xsd",
        # Theme files (common across document types)
        "theme": "ISO-IEC29500-4_2016/dml-main.xsd",
        # Drawing and media files
        "drawing": "ISO-IEC29500-4_2016/dml-main.xsd",
    }

    # Unified namespace constants
    MC_NAMESPACE = "http://schemas.openxmlformats.org/markup-compatibility/2006"
    XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"

    # Common OOXML namespaces used across validators
    PACKAGE_RELATIONSHIPS_NAMESPACE = (
        "http://schemas.openxmlformats.org/package/2006/relationships"
    )
    OFFICE_RELATIONSHIPS_NAMESPACE = (
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    CONTENT_TYPES_NAMESPACE = (
        "http://schemas.openxmlformats.org/package/2006/content-types"
    )

    # Folders where we should clean ignorable namespaces
    MAIN_CONTENT_FOLDERS = {"word", "ppt", "xl"}

    # All allowed OOXML namespaces (superset of all document types)
    OOXML_NAMESPACES = {
        "http://schemas.openxmlformats.org/officeDocument/2006/math",
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        "http://schemas.openxmlformats.org/schemaLibrary/2006/main",
        "http://schemas.openxmlformats.org/drawingml/2006/main",
        "http://schemas.openxmlformats.org/drawingml/2006/chart",
        "http://schemas.openxmlformats.org/drawingml/2006/chartDrawing",
        "http://schemas.openxmlformats.org/drawingml/2006/diagram",
        "http://schemas.openxmlformats.org/drawingml/2006/picture",
        "http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing",
        "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
        "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "http://schemas