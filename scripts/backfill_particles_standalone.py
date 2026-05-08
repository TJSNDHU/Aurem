#!/usr/bin/env python3
"""
AUREM Particles Backfill — STANDALONE production-ready version.

Run from any machine with network access to your Mongo Atlas cluster:
    export MONGO_URL='mongodb+srv://...'
    export DB_NAME='your_prod_db_name'
    pip install motor
    python3 backfill_particles_standalone.py --dry-run
    python3 backfill_particles_standalone.py

Idempotent. Re-runs are safe — only injects into rows missing the sentinel.
"""
import asyncio
import os
import re
import sys

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

_SENTINEL = "<!-- aurem-particles-v1 -->"

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
    for pat in _HERO_PATTERNS:
        m = pat.search(html)
        if not m:
            continue
        tag = m.group(1)
        if "aurem-hero-wrap" not in tag:
            if "class=" in tag:
                new_tag = re.sub(r"(class\s*=\s*[\"'])", r"\1aurem-hero-wrap ", tag, count=1)
            else:
                new_tag = tag[:-1] + ' class="aurem-hero-wrap">'
            html = html.replace(tag, new_tag, 1)
            tag = new_tag
        idx = html.find(tag) + len(tag)
        return html[:idx] + _CANVAS + html[idx:]
    return html


def inject_particles(html: str) -> str:
    if not html or _SENTINEL in html:
        return html or ""
    html = _inject_canvas(html)
    if "</body>" in html:
        return html.replace("</body>", _SCRIPT + "</body>", 1)
    return html + _SCRIPT


async def main(dry: bool) -> int:
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    q = {
        "status": {"$in": ["rendered", "published", "deployed"]},
        "rendered_html": {"$exists": True, "$ne": ""},
    }
    total = await db.auto_built_sites.count_documents(q)
    print(f"candidates: {total}")

    cur = db.auto_built_sites.find(q, {"_id": 0, "site_id": 1, "slug": 1, "rendered_html": 1})
    updated = already = unchanged = 0
    async for site in cur:
        sid = site.get("site_id")
        html = site.get("rendered_html") or ""
        if _SENTINEL in html:
            already += 1
            continue
        new_html = inject_particles(html)
        if new_html == html:
            unchanged += 1
            continue
        if not dry:
            await db.auto_built_sites.update_one(
                {"site_id": sid}, {"$set": {"rendered_html": new_html}}
            )
        updated += 1

    client.close()
    print(
        f"DONE · updated={updated} · already_injected={already} "
        f"· no_hero_container={unchanged} · dry={dry}"
    )
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(asyncio.run(main(dry)))
