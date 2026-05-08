"""
Unlinked-Mentions Service — iter 282al-4.

Finds sites that mention a business by name but don't link to it. These are
free backlink opportunities we can either surface as an outreach hook (for
leads) or reclaim via an email outreach (for clients).

Search stack (tries in order; each falls through on miss):
  1) webclaw.search()            — primary, when WEBCLAW_API_KEY is set
  2) Google Custom Search JSON   — when GOOGLE_API_KEY + GOOGLE_CSE_ID set
  3) DuckDuckGo HTML via webclaw — last-resort scrape, no key needed

Every public function never raises. On any failure returns an empty-result
shell with an `error` key.

Public surface:
  • scan_for_unlinked_mentions(business_name, website_url, db, limit=20)
  • extract_mention_context(html, business_name) → str
  • get_reclamation_status(db, client_bin)
  • update_mention_status(db, mention_id, status, notes="")
  • send_reclamation_outreach(db, mention_id, lead)
  • ensure_mention_indexes(db)
  • unlinked_mentions_health(db)
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

COLLECTION_MAIN = "unlinked_mentions"
COLLECTION_HIST = "mention_status_history"
TTL_MAIN_DAYS = 90
TTL_HIST_DAYS = 365

ALLOWED_STATUSES = (
    "pending", "outreach_sent", "reclaimed", "ignored",
)

# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────
def _extract_domain(url: str) -> str:
    if not url:
        return ""
    try:
        p = urlparse(url if "://" in url else f"https://{url}")
        return (p.netloc or "").lower().replace("www.", "")
    except Exception:
        return ""


def extract_mention_context(html: str, business_name: str) -> str:
    """Find the sentence containing `business_name` and return up to 200
    chars of surrounding text. Strips HTML tags before matching."""
    if not html or not business_name:
        return ""
    try:
        # Strip tags + collapse whitespace
        text = re.sub(r"<script.*?</script>|<style.*?</style>", " ",
                       html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        low_text = text.lower()
        low_name = business_name.lower()
        idx = low_text.find(low_name)
        if idx < 0:
            return ""

        # Window 100 chars before and after the match
        start = max(0, idx - 100)
        end = min(len(text), idx + len(business_name) + 100)
        snippet = text[start:end].strip()
        return snippet[:200]
    except Exception as e:
        logger.debug(f"[mentions] extract_context failed: {e}")
        return ""


# ─────────────────────────────────────────────────────────────────────
# Search providers — each returns list[str] of URLs
# ─────────────────────────────────────────────────────────────────────
async def _webclaw_search(query: str, limit: int) -> list[str]:
    try:
        from services.webclaw_client import get_client, is_configured
        if not is_configured():
            return []
        cli = get_client()
        if cli is None:
            return []
        resp = await cli.search(query, limit=limit)  # type: ignore[attr-defined]
        out: list[str] = []
        # Response shapes vary by SDK version — pull URLs defensively
        data = getattr(resp, "results", None) or resp
        if isinstance(data, dict):
            data = data.get("results") or data.get("data") or []
        if isinstance(data, list):
            for r in data:
                if isinstance(r, dict):
                    u = r.get("url") or r.get("link")
                    if u:
                        out.append(u)
                elif isinstance(r, str):
                    out.append(r)
        return out[:limit]
    except Exception as e:
        logger.debug(f"[mentions] webclaw search failed: {e}")
        return []


async def _google_cse_search(query: str, limit: int) -> list[str]:
    api = os.environ.get("GOOGLE_API_KEY", "").strip()
    cx = os.environ.get("GOOGLE_CSE_ID", "").strip()
    if not api or not cx:
        return []
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                "https://www.googleapis.com/customsearch/v1",
                params={"q": query, "key": api, "cx": cx,
                          "num": min(10, limit)},
            )
            if r.status_code != 200:
                logger.debug(f"[mentions] google cse {r.status_code}")
                return []
            items = (r.json() or {}).get("items") or []
            return [it.get("link") for it in items if it.get("link")][:limit]
    except Exception as e:
        logger.debug(f"[mentions] google cse failed: {e}")
        return []


async def _duckduckgo_search(query: str, limit: int) -> list[str]:
    """Last-resort scrape. Uses webclaw if available, else raw httpx."""
    ddg = f"https://duckduckgo.com/html/?q={query.replace(' ', '+')}"
    html = ""
    try:
        from services.webclaw_client import get_client, is_configured
        if is_configured():
            cli = get_client()
            if cli is not None:
                try:
                    r = await cli.scrape(ddg, formats=["html"])
                    html = (getattr(r, "html", None)
                             or getattr(r, "content", None) or "")
                except Exception:
                    pass
    except Exception:
        pass

    if not html:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                            headers={"User-Agent": "Mozilla/5.0"}) as c:
                r = await c.get(ddg)
                html = r.text or ""
        except Exception as e:
            logger.debug(f"[mentions] ddg fallback failed: {e}")
            return []

    # DDG html: <a class="result__a" href="...">
    urls = re.findall(r'href="(https?://[^"]+)"', html)
    # DDG redirects look like /l/?uddg=<encoded>
    cleaned = []
    for u in urls:
        if "duckduckgo.com" in u or "duckduck" in u:
            continue
        if u.startswith(("https://", "http://")):
            cleaned.append(u)
        if len(cleaned) >= limit:
            break
    return cleaned


async def _search_mentions(business_name: str, domain: str,
                            limit: int) -> tuple[list[str], str]:
    """Try each provider in priority order. Returns (urls, provider_name)."""
    query = f'"{business_name}" -site:{domain}' if domain else f'"{business_name}"'
    for provider_name, fn in (
        ("webclaw",    _webclaw_search),
        ("google_cse", _google_cse_search),
        ("duckduckgo", _duckduckgo_search),
    ):
        urls = await fn(query, limit)
        if urls:
            return urls, provider_name
    return [], "none"


# ─────────────────────────────────────────────────────────────────────
# Per-URL link check
# ─────────────────────────────────────────────────────────────────────
async def _check_url_for_link(url: str, domain: str) -> tuple[bool, str]:
    """Returns (has_link, raw_html_or_empty)."""
    if not url or not domain:
        return (False, "")
    html = ""
    try:
        from services.webclaw_client import get_client, is_configured
        if is_configured():
            cli = get_client()
            if cli is not None:
                try:
                    r = await cli.scrape(url, formats=["html"])
                    html = (getattr(r, "html", None)
                             or getattr(r, "content", None) or "")
                except Exception as e:
                    logger.debug(f"[mentions] webclaw scrape {url}: {e}")
    except Exception:
        pass

    if not html:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10, follow_redirects=True,
                                            headers={"User-Agent": "Mozilla/5.0"}) as c:
                r = await c.get(url)
                html = r.text or ""
        except Exception as e:
            logger.debug(f"[mentions] httpx scrape {url}: {e}")
            return (False, "")

    # Detect both bare-domain refs and full-link anchors
    low = html.lower()
    has_link = (f"href=\"http://{domain}" in low
                 or f"href=\"https://{domain}" in low
                 or f"href=\"//{domain}" in low
                 or f"href='http://{domain}" in low
                 or f"href='https://{domain}" in low)
    return (has_link, html)


# ─────────────────────────────────────────────────────────────────────
# Public: scan
# ─────────────────────────────────────────────────────────────────────
async def scan_for_unlinked_mentions(
    business_name: str,
    website_url: str,
    db,
    limit: int = 20,
) -> dict:
    """Find sites that mention `business_name` but don't link to
    `website_url`. Upserts one scan per (business_name, date). Never
    raises — on failure returns a shell with `error` set."""
    result_shell = {
        "business_name":  business_name or "",
        "website_url":    website_url or "",
        "total_unlinked": 0,
        "mentions":       [],
        "scan_date":      datetime.now(timezone.utc),
        "cached":         False,
        "provider":       None,
        "error":          None,
    }
    if not business_name or not website_url:
        result_shell["error"] = "business_name and website_url are required"
        return result_shell

    domain = _extract_domain(website_url)

    # ── Cache: one scan per business per calendar day ──
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    # Lock scan_date to start-of-day so upserts dedupe cleanly.
    result_shell["scan_date"] = today_start
    if db is not None:
        try:
            cached = await db[COLLECTION_MAIN].find_one(
                {"business_name": business_name,
                 "scan_date": {"$gte": today_start}},
                projection={"_id": 0},
                sort=[("scan_date", -1)],
            )
            if cached:
                out = {**result_shell, **cached, "cached": True}
                out["total_unlinked"] = cached.get("total_unlinked", 0)
                out["mentions"] = cached.get("mentions") or []
                return out
        except Exception as e:
            logger.debug(f"[mentions] cache lookup failed: {e}")

    # ── Search ──
    urls, provider = await _search_mentions(business_name, domain, limit)
    result_shell["provider"] = provider
    if not urls:
        result_shell["error"] = f"no search results ({provider})"
        # Persist the empty scan (upsert!) so we don't re-query for a day
        if db is not None:
            try:
                await db[COLLECTION_MAIN].update_one(
                    {"business_name": business_name,
                     "scan_date":     today_start},
                    {"$set": {
                        "business_name":  business_name,
                        "website_url":    website_url,
                        "mentions":       [],
                        "total_unlinked": 0,
                        "scan_date":      today_start,
                        "provider":       provider,
                        "error":          result_shell["error"],
                        "ts":             datetime.now(timezone.utc),
                    }},
                    upsert=True,
                )
            except Exception:
                pass
        return result_shell

    # ── Per-URL link check ──
    mentions = []
    for u in urls:
        try:
            has_link, html = await _check_url_for_link(u, domain)
            if has_link:
                continue
            ctx = extract_mention_context(html, business_name)
            if not ctx:
                # If we scraped but found no context, skip — likely noise.
                continue
            mentions.append({
                "mention_id":      str(uuid.uuid4())[:12],
                "url":             u,
                "domain":          _extract_domain(u),
                "has_link":        False,
                "mention_context": ctx,
                "status":          "pending",
                "discovered_at":   datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.debug(f"[mentions] per-url check failed {u}: {e}")
            continue

    result_shell["mentions"] = mentions
    result_shell["total_unlinked"] = len(mentions)

    # ── Persist ──
    if db is not None:
        try:
            await db[COLLECTION_MAIN].update_one(
                {"business_name": business_name,
                 "scan_date":     today_start},
                {"$set": {
                    "business_name":  business_name,
                    "website_url":    website_url,
                    "mentions":       mentions,
                    "total_unlinked": len(mentions),
                    "scan_date":      today_start,
                    "provider":       provider,
                    "ts":             datetime.now(timezone.utc),
                }},
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"[mentions] persist failed: {e}")

    return result_shell


# ─────────────────────────────────────────────────────────────────────
# Public: status + reclamation
# ─────────────────────────────────────────────────────────────────────
async def get_reclamation_status(db, client_bin: str) -> dict:
    """Return all unlinked mentions for a client grouped by status."""
    buckets = {"pending": [], "outreach_sent": [],
                "reclaimed": [], "ignored": []}
    if db is None or not client_bin:
        return buckets
    try:
        cursor = db[COLLECTION_MAIN].find(
            {"client_bin": client_bin},
            projection={"_id": 0},
        ).sort("ts", -1)
        docs = await cursor.to_list(length=100)
        for d in docs:
            for m in (d.get("mentions") or []):
                st = m.get("status") or "pending"
                if st in buckets:
                    buckets[st].append(m)
    except Exception as e:
        logger.debug(f"[mentions] status fetch failed: {e}")
    return buckets


async def update_mention_status(db, mention_id: str,
                                  status: str, notes: str = "") -> bool:
    """Update one mention's status. Logs the change to history."""
    if db is None or not mention_id:
        return False
    if status not in ALLOWED_STATUSES:
        return False
    try:
        # Find the parent doc by mention_id
        parent = await db[COLLECTION_MAIN].find_one(
            {"mentions.mention_id": mention_id},
            projection={"_id": 0, "business_name": 1,
                          "scan_date": 1, "mentions": 1},
        )
        if not parent:
            return False
        updated = await db[COLLECTION_MAIN].update_one(
            {"mentions.mention_id": mention_id},
            {"$set": {
                "mentions.$.status":     status,
                "mentions.$.updated_at": datetime.now(timezone.utc),
            }},
        )
        try:
            await db[COLLECTION_HIST].insert_one({
                "mention_id":    mention_id,
                "business_name": parent.get("business_name"),
                "status":        status,
                "notes":         notes[:500],
                "ts":            datetime.now(timezone.utc),
            })
        except Exception:
            pass
        return bool(updated.modified_count or updated.matched_count)
    except Exception as e:
        logger.debug(f"[mentions] update_status failed: {e}")
        return False


async def send_reclamation_outreach(db, mention_id: str,
                                      lead: dict) -> dict:
    """Compose and (mark as) send a link-reclamation email. Uses the
    existing `compose_outreach()` pipeline with a bespoke scan_content
    hint so the LLM references the actual mention context.
    """
    shell = {"sent": False, "message_preview": None, "error": None}
    if not mention_id or not lead:
        shell["error"] = "mention_id + lead required"
        return shell
    if db is None:
        shell["error"] = "db unavailable"
        return shell
    try:
        parent = await db[COLLECTION_MAIN].find_one(
            {"mentions.mention_id": mention_id},
            projection={"_id": 0, "business_name": 1, "website_url": 1,
                          "mentions": 1},
        )
        if not parent:
            shell["error"] = "mention not found"
            return shell
        mention = next((m for m in (parent.get("mentions") or [])
                         if m.get("mention_id") == mention_id), None)
        if not mention:
            shell["error"] = "mention not found in parent doc"
            return shell

        biz = parent.get("business_name") or lead.get("business_name") or ""
        site = parent.get("website_url") or lead.get("website") or ""
        ctx = mention.get("mention_context") or ""
        target_url = mention.get("url") or ""

        hint = (
            f"This site ({target_url}) mentions {biz} without linking to "
            f"{site}. Write a friendly, grateful email asking the owner "
            "to add a link. Do NOT be demanding. Reference the specific "
            f"mention: '{ctx[:160]}'. Keep it under 120 words."
        )

        from services.outreach_composer import compose_outreach
        composed = await compose_outreach(
            lead={**lead, "business_name": biz, "website": site},
            channel="email", step=1, db=db,
            scan_content=hint,
        )
        body = composed.get("body") or ""
        subject = composed.get("subject") or f"Quick thanks from {biz}"
        preview = (body[:200] + "…") if len(body) > 200 else body
        shell.update({
            "sent":            True,
            "message_preview": preview,
            "subject":         subject,
            "fallback_used":   composed.get("fallback_used"),
        })

        # Mark as outreach_sent
        await update_mention_status(
            db, mention_id, "outreach_sent",
            notes=f"auto-composed ({composed.get('model','?')})",
        )
        return shell
    except Exception as e:
        logger.warning(f"[mentions] reclamation outreach failed: {e}")
        shell["error"] = f"{type(e).__name__}: {str(e)[:160]}"
        return shell


# ─────────────────────────────────────────────────────────────────────
# Indexes + health
# ─────────────────────────────────────────────────────────────────────
async def ensure_mention_indexes(db) -> None:
    """TTL on both collections. Idempotent."""
    if db is None:
        return
    try:
        await db[COLLECTION_MAIN].create_index(
            [("ts", 1)], expireAfterSeconds=TTL_MAIN_DAYS * 24 * 3600,
            name="ts_ttl",
        )
        await db[COLLECTION_MAIN].create_index(
            [("business_name", 1), ("scan_date", -1)],
            name="biz_scandate",
        )
        await db[COLLECTION_MAIN].create_index(
            [("client_bin", 1)], name="client_bin",
        )
        await db[COLLECTION_HIST].create_index(
            [("ts", 1)], expireAfterSeconds=TTL_HIST_DAYS * 24 * 3600,
            name="ts_ttl",
        )
    except Exception as e:
        logger.debug(f"[mentions] index skipped: {e}")


async def unlinked_mentions_health(db) -> dict:
    if db is None:
        return {"ok": False, "status": "red", "detail": "db unavailable"}
    try:
        count = await db[COLLECTION_MAIN].count_documents({})
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        recent = await db[COLLECTION_MAIN].count_documents(
            {"ts": {"$gte": cutoff}},
        )
    except Exception as e:
        return {"ok": False, "status": "red",
                "detail": f"query failed: {type(e).__name__}"}
    if count == 0:
        return {"ok": True, "status": "green",
                "detail": "ready · awaiting first scan (manual or cron-driven)",
                "total_scans": 0, "recent_7d": 0}
    return {
        "ok":          True,
        "status":      "green" if recent > 0 else "yellow",
        "detail":      f"{count} scans total, {recent} in last 7d",
        "total_scans": count,
        "recent_7d":   recent,
    }


# ─────────────────────────────────────────────────────────────────────
# Sync wrappers for pytest
# ─────────────────────────────────────────────────────────────────────
def _run_sync(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                return ex.submit(lambda: asyncio.run(coro)).result()
    except RuntimeError:
        pass
    return asyncio.run(coro)


def scan_sync(business_name, website_url, db, limit=20):
    return _run_sync(scan_for_unlinked_mentions(
        business_name, website_url, db, limit,
    ))


def update_status_sync(db, mention_id, status, notes=""):
    return _run_sync(update_mention_status(db, mention_id, status, notes))


def send_outreach_sync(db, mention_id, lead):
    return _run_sync(send_reclamation_outreach(db, mention_id, lead))


__all__ = [
    "scan_for_unlinked_mentions",
    "extract_mention_context",
    "get_reclamation_status",
    "update_mention_status",
    "send_reclamation_outreach",
    "ensure_mention_indexes",
    "unlinked_mentions_health",
    "scan_sync",
    "update_status_sync",
    "send_outreach_sync",
    "COLLECTION_MAIN",
    "COLLECTION_HIST",
    "ALLOWED_STATUSES",
]
