#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "huggingface_hub",
#     "pyyaml",
#     "requests",
#     "python-dotenv",
# ]
# ///
"""
Paper Manager for Hugging Face Hub
Manages paper indexing, linking, authorship, and article creation.
"""

import argparse
import os
import sys
import re
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

try:
    from huggingface_hub import HfApi, hf_hub_download, get_token
    import yaml
    import requests
    from dotenv import load_dotenv
except ImportError as e:
    print(f"Error: Missing required dependency: {e}")
    print("Tip: run this script with `uv run scripts/paper_manager.py ...`.")
    sys.exit(1)

# Load environment variables
load_dotenv()


class PaperManager:
    """Manages paper publishing operations on Hugging Face Hub."""

    def __init__(self, hf_token: Optional[str] = None):
        """Initialize Paper Manager with HF token."""
        self.token = hf_token or os.getenv("HF_TOKEN") or get_token()
        if not self.token:
            print("Warning: No HF_TOKEN found. Some operations will fail.")
        self.api = HfApi(token=self.token)

    def index_paper(self, arxiv_id: str) -> Dict[str, Any]:
        """
        Index a paper on Hugging Face from arXiv.

        Args:
            arxiv_id: arXiv identifier (e.g., "2301.12345")

        Returns:
            dict: Status information
        """
        # Clean and validate arXiv ID
        try:
            arxiv_id = self._clean_arxiv_id(arxiv_id)
        except ValueError as e:
            print(f"Error: {e}")
            return {"status": "error", "message": str(e)}

        print(f"Indexing paper {arxiv_id} on Hugging Face...")

        # Check if paper exists
        paper_url = f"https://huggingface.co/papers/{arxiv_id}"

        try:
            response = requests.get(paper_url, timeout=10)
            if response.status_code == 200:
                print(f"✓ Paper already indexed at {paper_url}")
                return {"status": "exists", "url": paper_url}
            else:
                print(f"Paper not indexed. Visit {paper_url} to trigger indexing.")
                print("The paper will be automatically indexed when you first visit the URL.")
                return {"status": "not_indexed", "url": paper_url, "action": "visit_url"}
        except requests.RequestException as e:
            print(f"Error checking paper status: {e}")
            return {"status": "error", "message": str(e)}

    def check_paper(self, arxiv_id: str) -> Dict[str, Any]:
        """
        Check if a paper exists on Hugging Face.

        Args:
            arxiv_id: arXiv identifier

        Returns:
            dict: Paper status and metadata
        """
        try:
            arxiv_id = self._clean_arxiv_id(arxiv_id)
        except ValueError as e:
            return {"exists": False, "error": str(e)}
        paper_url = f"https://huggingface.co/papers/{arxiv_id}"

        try:
            response = requests.get(paper_url, timeout=10)
            if response.status_code == 200:
                return {
                    "exists": True,
                    "url": paper_url,
                    "arxiv_id": arxiv_id,
                    "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}"
                }
            else:
                return {
                    "exists": False,
                    "arxiv_id": arxiv_id,
                    "index_url": paper_url,
                    "message": f"Visit {paper_url} to index this paper"
                }
        except requests.RequestException as e:
            return {"exists": False, "error": str(e)}

    def link_paper_to_repo(
        self,
        repo_id: str,
        arxiv_id: str,
        repo_type: str = "model",
        citation: Optional[str] = None,
        create_pr: bool = False
    ) -> Dict[str, Any]:
        """
        Link a paper to a model/dataset/space repository.

        Args:
            repo_id: Repository identifier (e.g., "username/repo-name")
            arxiv_id: arXiv identifier
            repo_type: Type of repository ("model", "dataset", or "space")
            citation: Optional full citation text
            create_pr: Create a PR instead of direct commit

        Returns:
            dict: Operation status
        """
        try:
            arxiv_id = self._clean_arxiv_id(arxiv_id)
        except ValueError as e:
            print(f"Error: {e}")
            return {"status": "error", "message": str(e)}

        print(f"Linking paper {arxiv_id} to {repo_type} {repo_id}...")

        try:
            # Download current README
            readme_path = hf_hub_download(
                repo_id=repo_id,
                filename="README.md",
                repo_type=repo_type,
                token=self.token
            )

            with open(readme_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Parse or create YAML frontmatter
            updated_content = self._add_paper_to_readme(content, arxiv_id, citation)

            # Upload updated README
            commit_message = f"Add paper reference: arXiv:{arxiv_id}"

            if create_pr:
                # Create PR (not implemented in basic version)
                print("PR creation not yet implemented. Committing directly.")

            self.api.upload_file(
                path_or_fileobj=updated_content.encode('utf-8'),
                path_in_repo="README.md",
                repo_id=repo_id,
                repo_type=repo_type,
                commit_message=commit_message,
                token=self.token
            )

            paper_url = f"https://huggingface.co/papers/{arxiv_id}"
            repo_url = f"https://huggingface.co/{repo_id}"

            print(f"✓ Successfully linked paper to repository")
            print(f"  Paper: {paper_url}")
            print(f"  Repo: {repo_url}")

            return {
                "status": "success",
                "paper_url": paper_url,
                "repo_url": repo_url,
                "arxiv_id": arxiv_id
            }

        except Exception as e:
            print(f"Error linking paper: {e}")
            return {"status": "error", "message": str(e)}

    def _add_paper_to_readme(
        self,
        content: str,
        arxiv_id: str,
        citation: Optional[str] = None
    ) -> str:
        """
        Add paper reference to README content.

        Args:
            content: Current README content
            arxiv_id: arXiv identifier
            citation: Optional citation text

        Returns:
            str: Updated README content
        """
        arxiv_url = f"https://arxiv.org/abs/{arxiv_id}"
        hf_paper_url = f"https://huggingface.co/papers/{arxiv_id}"

        # Check if YAML frontmatter exists
        yaml_pattern = r'^---\s*\n(.*?)\n---\s*\n'
        match = re.match(yaml_pattern, content, re.DOTALL)

        if match:
            # YAML exists, check if paper already referenced
            if arxiv_id in content:
                print(f"Paper {arxiv_id} already referenced in README")
                return content

            # Add to existing content (after YAML)
            yaml_end = match.end()
            before = content[:yaml_end]
            after = content[yaml_end:]
        else:
            # No YAML, add minimal frontmatter
            yaml_content = "---\n---\n\n"
            before = yaml_content
            after = content

        # Add paper reference section with boundary markers
        paper_section = "\n<!-- paper-manager:start -->\n"
        paper_section += f"## Paper\n\n"
        paper_section += f"This {'model' if 'model' in content.lower() else 'work'} is based on research presented in:\n\n"
        paper_section += f"**[View on arXiv]({arxiv_url})** | "
        paper_section += f"**[View on Hugging Face]({hf_paper_url})**\n\n"

        if citation:
            safe_citation = self._sanitize_text(citation)
            paper_section += f"### Citation\n\n```bibtex\n{safe_citation}\n```\n\n"

        paper_section += "<!-- paper-manager:end -->\n"

        # Insert after YAML, before main content
        updated_content = before + paper_section + after

        return updated_content

    def _load_template(self, template: str) -> Optional[str]:
        """Load a template file by name, returning its content or None on failure."""
        template_dir = Path(__file__).parent.parent / "templates"
        template_file = template_dir / f"{template}.md"

        if not template_file.exists():
            print(f"Error: Template '{template}' not found at {template_file}")
            return None

        with open(template_file, 'r', encoding='utf-8') as f:
            return f.read()

    def _prepare_template_values(
        self,
        title: str,
        authors: Optional[str],
        abstract: Optional[str]
    ) -> Dict[str, str]:
        """Prepare sanitized values for template substitution."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        authors_val = authors if authors else "Your Name"
        abstract_val = abstract if abstract else "Abstract to be written..."

        return {
            "title": title,
            "authors": authors_val,
            "abstract": abstract_val,
            "safe_title_body": self._sanitize_text(title),
            "safe_authors_body": self._sanitize_text(authors_val),
            "safe_abstract_body": self._sanitize_text(abstract_val),
            "date": date_str,
        }

    def _render_template(self, template_content: str, values: Dict[str, str]) -> str:
        """Render a template by substituting placeholders with sanitized values."""
        # Split frontmatter from body for context-aware escaping
        fm_pattern = r'^(---\s*\n)(.*?\n)(---\s*\n)'
        fm_match = re.match(fm_pattern, template_content, re.DOTALL)

        if fm_match:
            fm_open, fm_body, fm_close = fm_match.group(1), fm_match.group(2), fm_match.group(3)
            body = template_content[fm_match.end():]

            # YAML-escape values in frontmatter
            fm_body = fm_body.replace("{{TITLE}}", self._escape_yaml_value(values["title"]))
            fm_body = fm_body.replace("{{AUTHORS}}", self._escape_yaml_value(values["authors"]))
            fm_body = fm_body.replace("{{DATE}}", values["date"])

            # Sanitize values in body
            body = body.replace("{{TITLE}}", values["safe_title_body"])
            body = body.replace("{{AUTHORS}}", values["safe_authors_body"])
            body = body.replace("{{ABSTRACT}}", values["safe_abstract_body"])
            body = body.replace("{{DATE}}", values["date"])

            return fm_open + fm_body + fm_close + body
        else:
            # No frontmatter — sanitize everything
            content = template_content.replace("{{TITLE}}", values["safe_title_body"])
            content = content.replace("{{DATE}}", values["date"])
            content = content.replace("{{AUTHORS}}", values["safe_authors_body"])
            content = content.replace("{{ABSTRACT}}", values["safe_abstract_body"])
            return content

    def create_research_article(
        self,
        template: str,
        title: str,
        output: str,
        authors: Optional[str] = None,
        abstract: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a research article from template.

        Args:
            template: Template name ("standard", "modern", "arxiv", "ml-report")
            title: Paper title
            output: Output filename
            authors: Comma-separated author names
            abstract: Abstract text

        Returns:
            dict: Creation status
        """
        print(f"Creating research article with '{template}' template...")

        template_content = self._load_template(template)
        if template_content is None:
            return {
                "status": "error",
                "message": f"Template '{template}' not found"
            }

        values = self._prepare_template_values(title, authors, abstract)
        content = self._render_template(template_content, values)

        with open(output, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✓ Research article created at {output}")

        return {
            "status": "success",
            "output": output,
            "template": template
        }

    def get_arxiv_info(self, arxiv_id: str) -> Dict[str, Any]:
        """
        Fetch paper information from arXiv API.

        Args:
            arxiv_id: arXiv identifier

        Returns:
            dict: Paper metadata
        """
        try:
            arxiv_id = self._clean_arxiv_id(arxiv_id)
        except ValueError as e:
            return {"error": str(e)}
        api_url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"

        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()

            # Parse XML response (simplified)
            content = response.text

            # Extract basic info with regex (proper XML parsing would be better)
            title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL)
            authors_matches = re.findall(r'<name>(.*?)</name>', content)
            summary_match = re.search(r'<summary>(.*?)</summary>', content, re.DOTALL)

            # Sanitize all text extracted from the external API
            raw_title = title_match.group(1).strip() if title_match else None
            raw_authors = authors_matches[1:] if len(authors_matches) > 1 else []
            raw_abstract = summary_match.group(1).strip() if summary_match else None

            return {
                "arxiv_id": arxiv_id,
                "title": self._sanitize_text(raw_title) if raw_title else None,
                "authors": [self._sanitize_text(a) for a in raw_authors],
                "abstract": self._sanitize_text(raw_abstract) if raw_abstract else None,
                "arxiv_url": f"https://arxiv.org/abs/{arxiv_id}",
                "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            }
        except Exception as e:
            return {"error": str(e)}

    def generate_citation(
        self,
        arxiv_id: str,
        format: str = "bibtex"
    ) -> str:
        """
        Generate citation for a paper.

        Args:
            arxiv_id: arXiv identifier
            format: Citation format ("bibtex", "apa", "mla")

        Returns:
            str: Formatted citation
        """
        try:
            arxiv_id = self._clean_arxiv_id(arxiv_id)
        except ValueError as e:
            return f"Error: {e}"

        info = self.get_arxiv_info(arxiv_id)

        if "error" in info:
            return f"Error fetching paper info: {info['error']}"

        if format == "bibtex":
            # Generate BibTeX citation
            key = f"arxiv{arxiv