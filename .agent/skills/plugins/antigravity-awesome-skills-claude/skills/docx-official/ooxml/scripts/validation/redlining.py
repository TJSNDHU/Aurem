"""
Validator for tracked changes in Word documents.
"""

import subprocess
import tempfile
import zipfile
from pathlib import Path

import defusedxml.ElementTree as ET


class RedliningValidator:
    """Validator for tracked changes in Word documents."""

    def __init__(self, unpacked_dir, original_docx, verbose=False):
        self.unpacked_dir = Path(unpacked_dir)
        self.original_docx = Path(original_docx)
        self.verbose = verbose
        self.namespaces = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        }

    def validate(self):
        """Main validation method that returns True if valid, False otherwise."""
        # Verify unpacked directory exists and has correct structure
        modified_file = self.unpacked_dir / "word" / "document.xml"
        if not modified_file.exists():
            print(f"FAILED - Modified document.xml not found at {modified_file}")
            return False

        # First, check if there are any tracked changes by Claude to validate
        try:
            tree = ET.parse(modified_file)
            root = tree.getroot()

            # Check for w:del or w:ins tags authored by Claude
            del_elements = root.findall(".//w:del", self.namespaces)
            ins_elements = root.findall(".//w:ins", self.namespaces)

            # Filter to only include changes by Claude
            claude_del_elements = [
                elem
                for elem in del_elements
                if elem.get(f"{{{self.namespaces['w']}}}author") == "Claude"
            ]
            claude_ins_elements = [
                elem
                for elem in ins_elements
                if elem.get(f"{{{self.namespaces['w']}}}author") == "Cl