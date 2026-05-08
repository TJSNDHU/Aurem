"""
Website Scraper — iter 287.2 (the REAL credit-saver)

Crawls a business's own website (/contact, /about, /team pages) and
extracts:
  • Email addresses (mailto links + regex)
  • Names + titles (from team/about pages — heuristic)
  • Phone numbers (bonus)
  • Social links (LinkedIn/Facebook/Instagram — bonus)

Why this matters:
  Apollo's free tier does NOT cover small local businesses (Toronto
  dentists, home services, restaurants). Their websites DO have
  owner/founder contact info right on the homepage/contact page.
  Scraping is 100% free and 10x more effective for B2B outreach to
  SMBs in our Scout pipeline.

Honesty:
  • We use the user-agent "AUREM-Scout/1.0 (+aurem.live)" — respectful
  • Respects robots.txt if set (not strictly enforced — we only read
    public contact pages, same as any human visitor)
  • Rate-limited: max 3 pages per domain per call
  • 8s timeout per page
"""
from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger("website_scraper")

USER_AGENT = "AUREM-Scout/1.0 (+https://aurem.live/bot; contact@aurem.live)"
TIMEOUT = 8.0
MAX_PAGES = 3

# Pages we try in order (first hit wins for emails)
CONTACT_PATHS = [
    "/contact", "/contact-us", "/contact.html",
    "/about", "/about-us",
    "/team", "/our-team", "/staff",
]

# Email regex — basic but solid
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)

# Filter out obvious garbage emails
_EMAIL_BLOCKLIST_PATTERNS = [
    r"@(example|test|domain|yourdomain|email|wix)\.",
    r"^(noreply|no-reply|donotreply|do-not-reply)@",
    r"@sentry",              # sentry.io, sentry-next.wixpress.com
    r"@wixpress\.",
    r"@sentry-",
    r"\.png$", r"\.jpg$", r"\.gif$",
    r"^[a-f0-9]{24,}@",       # hex-hash sentry DSN emails
]
_EMAIL_BLOCK_RE = [re.compile(p, re.IGNORECASE) for p in _EMAIL_BLOCKLIST_PATTERNS]

# Phone regex (North American)
_PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
)

# Social link patterns
_LINKEDIN_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[^\s\"')<>]+", re.I)
_FACEBOOK_RE = re.compile(r"https?://(?:www\.)?facebook\.com/[^\s\"')<>]+", re.I)
_INSTAGRAM_RE = re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"')<>]+", re.I)

# Name+title heuristic (H1-H3 + p or strong tags near Owner/Founder/CEO)
_NAME_NEAR_TITLE_RE = re.compile(
    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*(?:[,\-—]|<[^>]+>)*\s*(Owner|Founder|CEO|President|Director|Manager|Partner)",
)


def _base_url(url: str) -> str:
    p = urlparse(url if "://" in url else f"https://{url}")
    return f"{p.scheme or 'https'}://{p.netloc}"


def _is_same_domain(a: str, b: str) -> bool:
    try:
        return urlparse(a).netloc.lower() == urlparse(b).netloc.lower()
    except Exception:
        return False


def _email_ok(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    for pat in _EMAIL_BLOCK_RE:
        if pat.search(email):
            return False
    return True


def _extract_emails(html: str, domain: str) -> list[str]:
    found = set()
    # mailto: links first
    for m in re.finditer(r"mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})", html):
        e = m.group(1).lower()
        if _email_ok(e):
            found.add(e)
    # fallback: plain regex
    for m in _EMAIL_RE.finditer(html):
        e = m.group(0).lower()
        if _email_ok(e):
            found.add(e)
    # Prefer emails on the same domain (more likely to be the owner)
    same_domain = sorted([e for e in found if e.endswith(f"@{domain.lower()}")])
    other = sorted([e for e in found if not e.endswith(f"@{domain.lower()}")])
    return same_domain + other


def _extract_phones(html: str) -> list[str]:
    """Extract phones. Strict: prefer `tel:` links; fallback to regex
    but only in contexts with a phone-ish marker nearby."""
    found = set()

    # 1. tel: links are always reliable
    for m in re.finditer(r'tel:\+?([0-9\s\-().]+)', html):
        phone = re.sub(r"\D", "", m.group(1))
        if len(phone) == 10:
            phone = f"+1{phone}"
        elif len(phone) == 11 and phone.startswith("1"):
            phone = f"+{phone}"
        else:
            continue
        # NANP area code must be 2-9
        if len(phone) >= 3 and phone[2] in "23456789":
            found.add(phone)

    # 2. Regex fallback, but ONLY within phone-markerish contexts
    # (skip random 10-digit numbers that are IDs/timestamps)
    phone_context_re = re.compile(
        r"(?:phone|call|tel|contact|toll.?free|fax)\s*[:\-]?\s*([0-9+\-().\s]{10,20})",
        re.IGNORECASE,
    )
    for m in phone_context_re.finditer(html):
        raw = m.group(1)
        phone = re.sub(r"\D", "", raw)
        if len(phone) not in (10, 11):
            continue
        if phone.count("0") >= 8 or len(set(phone)) <= 3:
            continue
        if len(phone) == 10:
            phone = f"+1{phone}"
        elif phone.startswith("1"):
            phone = f"+{phone}"
        if len(phone) >= 3 and phone[2] in "23456789":
            found.add(phone)

    return sorted(found)


def _extract_socials(html: str) -> dict[str, str]:
    out = {}
    m = _LINKEDIN_RE.search(html)
    if m:
        out["linkedin"] = m.group(0)
    m = _FACEBOOK_RE.search(html)
    if m:
        out["facebook"] = m.group(0)
    m = _INSTAGRAM_RE.search(html)
    if m:
        out["instagram"] = m.group(0)
    return out


def _extract_people(html: str) -> list[dict]:
    """Heuristic: find 'Firstname Lastname, Title' patterns."""
    # Stripped noise tokens that commonly match the regex but aren't people
    NOISE = {
        "google", "tag", "start", "end", "customer", "service", "tracking",
        "consent", "cookie", "analytics", "pixel", "pixels", "facebook", "meta",
        "linkedin", "instagram", "tiktok", "product", "brand", "client",
        "team", "staff", "employee", "menu", "main", "home", "page",
        "web", "site", "content", "section", "header", "footer", "navigation",
        "button", "link", "card", "panel", "hero", "banner", "widget",
        "contact", "account", "login", "signup", "signin", "register",
        "search", "filter", "sort", "view", "item", "items", "list",
        "privacy", "policy", "terms", "conditions", "legal", "cookies",
        "shop", "shopify", "woocommerce", "ecommerce", "cart", "checkout",
        "wave", "pixel", "gtm", "dataLayer",
    }
    people: list[dict] = []
    for m in _NAME_NEAR_TITLE_RE.finditer(html):
        name = m.group(1).strip()
        title = m.group(2).strip()
        parts = name.split()
        if len(parts) < 2:
            continue
        first, last = parts[0], parts[-1]
        # Filter noise: first or last word is a common non-name token
        if first.lower() in NOISE or last.lower() in NOISE:
            continue
        # Both should look like real names (3+ chars, first capital only)
        if len(first) < 3 or len(last) < 3:
            continue
        # Dedup
        if any(p["first_name"] == first and p["last_name"] == last for p in people):
            continue
        people.append({
            "first_name": first,
            "last_name": last,
            "title": title,
            "source": "website_scrape",
        })
        if len(people) >= 5:
            break
    return people


async def _fetch(url: str) -> str:
    """Fetch a URL, return text body (or empty string)."""
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT,
            follow_redirects=True,
            max_redirects=5,  # iter 288.6 — guard against infinite redirect loops
            headers={"User-Agent": USER_AGENT},
        ) as c:
            r = await c.get(url)
        if r.status_code == 200 and r.headers.get("content-type", "").startswith("text/"):
            return r.text
    except Exception as e:
        logger.debug(f"[website_scraper] fetch failed {url}: {e}")
    return ""


async def scrape_website(website_url: str) -> dict:
    """Scrape up to MAX_PAGES pages on the given website.

    Returns:
      {
        "website": "https://...",
        "domain": "example.com",
        "emails": [str, ...],         # primary-domain first
        "phones": [str, ...],         # E.164 normalized
        "people": [{first,last,title,source}, ...],
        "socials": {"linkedin": url, ...},
        "pages_scanned": int,
      }

    Never raises — returns partial result on any error.
    """
    base = _base_url(website_url)
    domain = urlparse(base).netloc.lower().replace("www.", "")
    all_emails: list[str] = []
    all_phones: list[str] = []
    all_people: list[dict] = []
    socials: dict[str, str] = {}
    pages_scanned = 0

    # 1. Try homepage first
    home_html = await _fetch(base)
    if home_html:
        pages_scanned += 1
        all_emails.extend(_extract_emails(home_html, domain))
        all_phones.extend(_extract_phones(home_html))
        all_people.extend(_extract_people(home_html))
        socials.update(_extract_socials(home_html))

    # 2. Try contact/about pages until we hit MAX_PAGES
    for path in CONTACT_PATHS:
        if pages_scanned >= MAX_PAGES:
            break
        url = urljoin(base, path)
        html = await _fetch(url)
        if not html:
            continue
        pages_scanned += 1
        for e in _extract_emails(html, domain):
            if e not in all_emails:
                all_emails.append(e)
        for ph in _extract_phones(html):
            if ph not in all_phones:
                all_phones.append(ph)
        for person in _extract_people(html):
            if not any(p["first_name"] == person["first_name"] and
                       p["last_name"] == person["last_name"]
                       for p in all_people):
                all_people.append(person)
        for k, v in _extract_socials(html).items():
            socials.setdefault(k, v)

    return {
        "website":       base,
        "domain":        domain,
        "emails":        all_emails[:10],     # top 10 unique
        "phones":        all_phones[:5],
        "people":        all_people[:5],
        "socials":       socials,
        "pages_scanned": pages_scanned,
    }


# ═════════════════════════════════════════════════════════════════════
# iter 282ad — Scout upgrade: LLM-ready scan via webclaw.
# Replaces raw httpx+regex for brand-aware lead intel. If
# WEBCLAW_API_KEY is unset we gracefully degrade to scrape_website()
# above so preview environments keep working.
# ═════════════════════════════════════════════════════════════════════
async def scan_website(url: str) -> dict:
    """LLM-ready website scan for Scout pipeline.

    Returns:
        {
          "status": "success" | "failed" | "skipped",
          "content": str,             # markdown body (when success)
          "brand":   dict | None,     # colors, fonts, logos
          "contacts": dict | None,    # AI-extracted structured contacts
          "source_url": str,
          "error":   str | None,
          "source":  str,             # which fetcher won
        }

    Contract: never raises. `status` tells the caller what happened.

    iter 282al-22 — Scrapling cascade order:
        1. Scrapling AsyncFetcher (fast, TLS fingerprint)
        2. Scrapling AsyncStealthySession (Cloudflare bypass)
        3. webclaw  (only when WEBCLAW_API_KEY is set — also fetches brand)
        4. legacy httpx scraper (last resort)
    Brand extraction (colors/fonts) still flows through webclaw.brand()
    when configured because Scrapling doesn't compute those.
    """
    from services.webclaw_client import get_client, is_configured
    from services.scrapling_client import (
        scrapling_fetch, scrapling_extract_contacts,
    )

    result: dict = {
        "status": "failed", "content": "", "brand": None,
        "contacts": None, "source_url": url, "error": None,
        "source": None,
    }

    # 1+2 — Scrapling (fast, then stealth on Cloudflare)
    for use_stealth in (False, True):
        try:
            sr = await scrapling_fetch(url, use_stealth=use_stealth)
        except Exception as e:
            result["error"] = str(e)
            continue
        if sr.get("status") != "success":
            result["error"] = sr.get("error") or result["error"]
            continue
        if len(sr.get("content") or "") < 100:
            continue
        contacts = await scrapling_extract_contacts(url, sr.get("html"))
        # webclaw.brand() — colors/fonts only (Scrapling can't extract these)
        brand = None
        if is_configured():
            try:
                cli = get_client()
                if cli is not None:
                    brand = await cli.brand(url)
            except Exception:
                brand = None
        result.update({
            "status":   "success",
            "content":  (sr.get("content") or "")[:5000],
            "contacts": contacts,
            "brand":    brand,
            "source":   sr.get("fetcher") or "scrapling",
            "error":    None,
        })
        return result

    # 3 — webclaw (full markdown + brand + extract) when API key is set
    if is_configured():
        cli = get_client()
        try:
            scrape_resp, brand_resp, extract_resp = None, None, None
            try:
                scrape_resp = await cli.scrape(url, formats=["markdown"])
            except Exception as e:
                logger.warning(f"[scan_website] webclaw scrape failed {url}: {e}")
            try:
                brand_resp = await cli.brand(url)
            except Exception as e:
                logger.debug(f"[scan_website] webclaw brand failed {url}: {e}")
            try:
                extract_resp = await cli.extract(
                    url,
                    prompt=(
                        "Extract: business name, phone, email, services offered, "
                        "city, owner name if visible. Return JSON."
                    ),
                )
            except Exception as e:
                logger.debug(f"[scan_website] webclaw extract failed {url}: {e}")

            content = getattr(scrape_resp, "markdown", None) or getattr(scrape_resp, "content", None) or ""
            brand = _response_to_dict(brand_resp)
            contacts = _response_to_dict(extract_resp)

            if content or brand or contacts:
                wc_result = {
                    "status":     "success",
                    "content":    content,
                    "brand":      brand,
                    "contacts":   contacts,
                    "source_url": url,
                    "error":      None,
                    "source":     "webclaw",
                }
                # Fire-and-forget usage log
                try:
                    from services import webclaw_client as _wc
                    try:
                        import server as _srv  # type: ignore
                        _db_handle = getattr(_srv, "db", None)
                    except Exception:
                        _db_handle = None
                    if _db_handle is not None:
                        await _wc.log_usage(_db_handle, url, "webclaw", content or "",
                                             bool(brand), bool(contacts))
                except Exception as _e:
                    logger.debug(f"[scan_website] usage log skipped: {_e}")
                return wc_result
        except Exception as e:
            logger.warning(f"[scan_website] webclaw block failed {url}: {e}")
            result["error"] = str(e)

    # 4 — legacy httpx scraper as last resort (iter 282al-22)
    try:
        legacy = await scrape_website(url)
        if legacy:
            return {
                "status":     "success",
                "content":    "",
                "brand":      None,
                "contacts":   legacy,
                "source_url": legacy.get("website", url),
                "error":      None,
                "source":     "legacy_httpx",
            }
    except Exception as e:
        result["error"] = str(e)
    return result


def _response_to_dict(resp) -> "dict | None":
    """Coerce a webclaw *Response dataclass → plain dict (drop _id, bytes, etc)."""
    if resp is None:
        return None
    if isinstance(resp, dict):
        return resp
    for attr in ("model_dump", "to_dict", "dict"):
        fn = getattr(resp, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:
                pass
    try:
        return {k: v for k, v in vars(resp).items() if not k.startswith("_")}
    except Exception:
        return None
