"""
AUREM — Gold Particles HTML injector (iter 305g)

Injects the hero-canvas particle animation into any AWB-rendered site
without changing content, colors, or layout.

Public API:
  inject_particles(html: str) -> str
      Idempotent. Safe no-op if already injected.
"""
from __future__ import annotations

import re

_SENTINEL = "<!-- aurem-particles-v1 -->"

# Script tag pointing to /static/js/particles.js. FastAPI already mounts
# /api/static/; frontend public/static is served on the same origin so
# /static/js/particles.js resolves in both dev and production.
_SCRIPT = (
    f"\n  {_SENTINEL}\n"
    "  <style>\n"
    "    .aurem-hero-wrap{position:relative;overflow:hidden;}\n"
    "    .aurem-hero-wrap > *:not(#aurem-particles){position:relative;z-index:2;}\n"
    "    #aurem-particles{position:absolute;inset:0;width:100%;height:100%;"
    "pointer-events:none;z-index:1;}\n"
    "  </style>\n"
    '  <script src="/static/js/particles.js" defer></script>\n'
)

# Candidate hero markers in order of specificity. First match wins.
_HERO_PATTERNS = [
    re.compile(r"(<section[^>]*\bclass\s*=\s*[\"'][^\"']*\bhero\b[^\"']*[\"'][^>]*>)", re.I),
    re.compile(r"(<header[^>]*\bclass\s*=\s*[\"'][^\"']*\bhero\b[^\"']*[\"'][^>]*>)", re.I),
    re.compile(r"(<div[^>]*\bclass\s*=\s*[\"'][^\"']*\bhero\b[^\"']*[\"'][^>]*>)", re.I),
    re.compile(r"(<section[^>]*\bid\s*=\s*[\"']hero[\"'][^>]*>)", re.I),
    re.compile(r"(<header[^>]*>)", re.I),
    re.compile(r"(<body[^>]*>)", re.I),
]

_CANVAS = '\n    <canvas id="aurem-particles"></canvas>\n    '


def _inject_canvas(html: str) -> str:
    """Insert the canvas as the first child of the best hero container."""
    for pat in _HERO_PATTERNS:
        m = pat.search(html)
        if not m:
            continue
        tag = m.group(1)
        # Add .aurem-hero-wrap class so CSS above auto-applies
        if "aurem-hero-wrap" not in tag:
            if "class=" in tag:
                new_tag = re.sub(
                    r"(class\s*=\s*[\"'])",
                    r"\1aurem-hero-wrap ",
                    tag,
                    count=1,
                )
            else:
                # Inject class attribute before closing >
                new_tag = tag[:-1] + ' class="aurem-hero-wrap">'
            html = html.replace(tag, new_tag, 1)
            tag = new_tag
        idx = html.find(tag) + len(tag)
        return html[:idx] + _CANVAS + html[idx:]
    return html  # no hero-like container; safer to skip canvas


def inject_particles(html: str) -> str:
    """Idempotent injector.

    - If the sentinel is already present → return unchanged.
    - Else injects <canvas> into the hero and appends style+script.
    """
    if not html or _SENTINEL in html:
        return html or ""

    html = _inject_canvas(html)

    # Append style + script. Prefer before </body>, else append at end.
    if "</body>" in html:
        return html.replace("</body>", _SCRIPT + "</body>", 1)
    return html + _SCRIPT
