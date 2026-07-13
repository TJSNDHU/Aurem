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
        "http://schemas.openxmlformats.org/presentationml/2006/main",
        "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "http://schemas.openxmlformats.org/officeDocument/2006/sharedTypes",
        "http://www.w3.org/XML/1998/namespace",
    }

    def __init__(self, unpacked_dir, original_file, verbose=False):
        self.unpacked_dir = Path(unpacked_dir).resolve()
        self.original_file = Path(original_file)
        self.verbose = verbose

        # Set schemas directory
        self.schemas_dir = Path(__file__).parent.parent.parent / "schemas"

        # Get all XML and .rels files
        patterns = ["*.xml", "*.rels"]
        self.xml_files = [
            f for pattern in patterns for f in self.unpacked_dir.rglob(pattern)
        ]

        if not self.xml_files:
            print(f"Warning: No XML files found in {self.unpacked_dir}")

    def validate(self):
        """Run all validation checks and return True if all pass."""
        raise NotImplementedError("Subclasses must implement the validate method")

    def validate_xml(self):
        """Validate that all XML files are well-formed."""
        errors = []

        for xml_file in self.xml_files:
            try:
                # Try to parse the XML file
                lxml.etree.parse(str(xml_file))
            except lxml.etree.XMLSyntaxError as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: "
                    f"Line {e.lineno}: {e.msg}"
                )
            except Exception as e:
                errors.append(
                    f"  {xml_file.relative_to(self.unpacked_dir)}: "
                    f"Unexpected error: {str(e)}"
                )

        if errors:
            print(f"FAILED - Found {len(errors)} XML violations:")
            for error in errors:
                print(error)
            return False
        else:
            if self.verbose:
                print("PASSED - All XML files are well-formed")
            return True

    def validate_namespaces(self):
        """Validate that namespace prefixes in Ignorable attributes are declared."""
        errors = []

        for xml_file in self.xml_files:
            try:
                root = lxml.etree.parse(str(xml_file)).getroot()
                declared = set(root.nsmap.keys()) - {None}  # Exclude default namespace

                for attr_val in [
                    v for k, v in root.attrib.items() if k.endswith("Ignorable")
                ]:
                    undeclared = set(attr_val.split()) - declared
                    errors.extend(
                        f"  {xml_file.relative_to(self.unpacked_dir)}: "
                        f"Namespace '{ns}' in Ignorable but not declared"
                        for ns in undeclared
                    )
            except lxml.etree.XMLSyntaxError:
                continue

        if errors:
            print(f"FAILED - {len(errors)} namespace issues:")
            for error in errors:
                print(error)
            return False
        if self.verbose:
            print("PASSED - All namespace prefixes properly declared")
        return True

    def _remove_alternate_content(self, root):
        """Remove all mc:AlternateContent elements from the tree."""
        mc_elements = root.xpath(
            ".//mc:AlternateContent", namespaces={"mc": self.MC_NAMESPACE}
        )
        for elem in mc_elements:
            elem.getparent().remove(elem)

    def _get_element_id(self, elem, attr_name):
        """Extract the ID value from an element's attributes."""
        for attr, value in elem.attrib.items():
            attr_local = (
                attr.split("}")[-1].lower()
                if "}" in attr
                else attr.lower()
            )
            if attr_local == attr_name:
                return value
        return None

    def _check_global_id_uniqueness(
        self, id_value, tag, elem, xml_file, global_ids, errors
    ):
        """Check and record global ID uniqueness violations."""
        if id_value in global_ids:
            prev_file, prev_line, prev_tag = global_ids[id_value]
            errors.append(
                f"  {xml_file.relative_to(self.unpacked_dir)}: "
                f"Line {elem.sourceline}: Global ID '{id_value}' in <{tag}> "
                f"already used in {prev_file} at line {prev_line} in <{prev_tag}>"
            )
        else:
            global_ids[id_value] = (
                xml_file.relative_to(self.unpacked_dir),
                elem.sourceline,
                tag,
            )

    def _check_file_id_uniqueness(
        self, id_value, tag, attr_name, elem, xml_file, file_ids, errors
    ):
        """Check and record file-level ID uniqueness violations."""
        key = (tag, attr_name)
        if key not in file_ids:
            file_ids[key] = {}

        if id_value in file_ids[key]:
            prev_line = file_ids[key][id_value]
            errors.append(
                f"  {xml_file.relative_to(self.unpacked_dir)}: "
                f"Line {elem.sourceline}: Duplicate {attr_name}='{id_value}' in <{tag}> "
                f"(first occurrence at line {prev_line})"
            )
        else:
            file_ids[key][id_value] = elem.sourceline

    def validate_unique_ids(self):
        """Validate that specific IDs are unique according to OOXML requirements."""
        errors = []
        global_ids = {}  # Track