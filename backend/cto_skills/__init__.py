"""
AUREM CTO Skills System.

Each skill is a self-contained, plain-Python function with:
  • clear docstring (one-line summary + when-to-use)
  • typed args / return
  • no side effects beyond its declared scope
  • registers itself with `@skill(name=...)`

The registry loader scans this package at import time and exposes a
unified `cto_skills.invoke(name, **kwargs)` entry point used by
`services.dev_cto_chat` to actually execute a skill the LLM picks.
"""
from .registry import skill, invoke, list_skills, manifest

# Import each skill module so its @skill decorator fires.
from . import read_codebase  # noqa: F401
from . import edit_file       # noqa: F401
from . import run_tests       # noqa: F401
from . import apollo_lead_search  # noqa: F401
from . import send_email_via_resend  # noqa: F401
from . import remember        # noqa: F401
from . import recall          # noqa: F401

__all__ = ["skill", "invoke", "list_skills", "manifest"]
