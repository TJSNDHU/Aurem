"""
AUREM Forensic Miner — Automated Lead Discovery & Outreach
=============================================================
Uses free APIs (DomainsDB + Tomba) to:
  1. Search domains by niche (skincare, beauty, etc.)
  2. Find owner emails via Tomba.io
  3. Generate store health report via web_fetch
  4. Queue outreach via Envoy Agent (WhatsApp + Email + Social)

Input: {niche: "beauty", limit: 10}
Output: list of stores with email + health score + outreach queued
"""
import os
import logging
import secrets
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_db = None


def set_db(database):
    global _db
    _db = database


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
    except Exception:
        pass
    return _db


NICHE_KEYWORDS = {
    "beauty": ["beauty", "skincare", "cosmetics", "makeup"],
    "skincare": ["skincare", "skin-care", "serum", "moisturizer"],
    "fashion": ["fashion", "clothing", "apparel", "boutique"],
    "health": ["health", "wellness", "supplement", "vitamin"],
    "fitness": ["fitness", "gym", "workout", "training"],
    "food": ["food", "organic", "snacks", "gourmet"],
    "tech": ["tech", "gadget", "electronics", "smart"],
    "pets": ["pets", "dog", "cat", "petcare"],
}


async def _search_domains(keyword: str, zone: str = "com", limit: int = 20) -> List[Dict]:
    """Find domains matching a niche via DuckDuckGo search + DomainsDB fallback."""
    # Primary: DuckDuckGo search for Shopify stores in niche
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        search_queries = [
            f"{keyword} shopify store site:myshopify.com",
            f"{keyword} online shop {zone}",
            f"best {keyword} stores ecommerce",
        ]
        domains = []
        seen = set()
        for q in search_queries:
            try:
                results = list(ddgs.text(q, max_results=limit))
                for r in results:
                    url = r.get("href", r.get("link", ""))
                    if not url:
                        continue
                    from urllib.parse import urlparse
                    parsed = urlparse(url)
                    dom = parsed.netloc.lstrip("www.")
                    if dom and dom not in seen and not dom.endswith((".google.com", ".youtube.com", ".facebook.com", ".wikipedia.org", ".amazon.com", ".reddit.com")):
                        seen.add(dom)
                        domains.append({
                            "domain": dom,
                            "title": r.get("title", ""),
                            "snippet": r.get("body", r.get("snippet", ""))[:150],
                            "source": "duckduckgo",
                        })
            except Exception:
                pass
            if len(domains) >= limit:
                break
        if domains:
            return domains[:limit]
    except Exception as e:
        logger.debug(f"[ForensicMiner] DDG search: {e}")

    # Fallback: DomainsDB
    from services.free_api_arsenal import search_domains
    result = await search_domains(keyword, zone, limit)
    return result.get("domains", [])


async def _find_emails(domain: str) -> Dict:
    """
    Find owner emails by scraping contact/about pages. 100% free, unlimited.
    Priority: Firecrawl (if key set) → web_fetch fallback (always free).
    Scrapes /contact, /about, /about-us for email patterns.
    """
    import re
    EMAIL_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
    CONTACT_PATHS = ["/contact", "/about", "/about-us", "/contact-us", "/team", ""]
    found_emails = set()
    organization = ""

    base_url = f"https://{domain}" if not domain.startswith("http") else domain

    # Try Firecrawl first (if key available — better extraction)
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if firecrawl_key:
        try:
            from services.tier1_upgrades import firecrawl_scrape
            for path in CONTACT_PATHS[:3]:
                result = await firecrawl_scrape(f"{base_url}{path}", formats=["markdown"])
                md = result.get("markdown", "")
                if md:
                    found_emails.update(EMAIL_RE.findall(md))
                    if not organization:
                        organization = result.get("metadata", {}).get("title", "")
                if found_emails:
                    break
        except Exception:
            pass

    # Fallback: web_fetch (always free, no key needed)
    if not found_emails:
        try:
            from services.mcp_extended_tools import web_fetch
            for path in CONTACT_PATHS:
                try:
                    data = await web_fetch(f"{base_url}{path}", extract="text", max_chars=5000)
                    text = data.get("text", "") or data.get("content", "")
                    if text:
                        found_emails.update(EMAIL_RE.findall(text))
                        if not organization:
                            organization = data.get("meta", {}).get("title", "")
                    if found_emails:
                        break
                except Exception:
                    continue
        except Exception:
            pass

    # Filter out common junk emails
    junk = {"noreply@", "no-reply@", "mailer-daemon@", "postmaster@", "webmaster@"}
    clean = [e for e in found_emails if not any(e.lower().startswith(j) for j in junk) and domain.split(".")[0] not in ["example"]]

    return {
        "domain": domain,
        "emails": [{"email": e, "type": "scraped", "confidence": 80, "source": "contact_page"} for e in list(clean)[:5]],
        "organization": organization,
        "total_found": len(clean),
        "method": "firecrawl" if firecrawl_key and clean else "web_fetch",
    }


async def _quick_health_scan(domain: str) -> Dict:
    """Quick SEO health check via web_fetch (free, no key)."""
    from services.mcp_extended_tools import web_fetch
    try:
        url = f"https://{domain}" if not domain.startswith("http") else domain
        data = await web_fetch(url, extract="meta", max_chars=500)
        if data.get("error"):
            return {"domain": domain, "score": 0, "reachable": False, "error": data["error"]}

        meta = data.get("meta", {})
        score = 0
        issues = []

        # Title check
        title = meta.get("title", "")
        if title:
            score += 25
        else:
            issues.append("missing_title")

        # Meta description check
        desc = meta.get("description", "")
        if desc:
            score += 25
            if len(desc) < 50:
                issues.append("short_meta_description")
                score -= 5
        else:
            issues.append("missing_meta_description")

        # OG tags check
        if meta.get("og_title"):
            score += 15
        else:
            issues.append("missing_og_tags")

        if meta.get("og_image"):
            score += 10
        else:
            issues.append("missing_og_image")

        # Base score for being reachable
        score += 25

        return {
            "domain": domain,
            "score": min(100, score),
            "reachable": True,
            "title": title[:80],
            "description": desc[:120],
            "issues": issues,
            "issue_count": len(issues),
        }
    except Exception as e:
        return {"domain": domain, "score": 0, "reachable": False, "error": str(e)}


async def _extract_contacts(domain: str) -> Dict:
    """Extract social profiles and contact info from a domain."""
    from services.mcp_extended_tools import web_extract_contacts
    try:
        result = await web_extract_contacts(f"https://{domain}")
        return {
            "emails_from_site": result.get("emails", []),
            "phones": result.get("phones", []),
            "social": result.get("social", {}),
        }
    except Exception:
        return {"emails_from_site": [], "phones": [], "social": {}}


async def _corrective_enrich(stores: List[Dict], thin_threshold: int = 2) -> List[Dict]:
    """
    Corrective RAG pattern (inspired by firecrawl-agent):
    Grade each store's data quality. If 'thin' (no emails + low score),
    attempt Firecrawl deep-crawl to extract more intel.
    Firecrawl is optional — gracefully skips if no key.
    """
    firecrawl_key = os.environ.get("FIRECRAWL_API_KEY", "")
    if not firecrawl_key:
        return stores  # No key, skip corrective enrichment

    thin_stores = [s for s in stores if s.get("email_count", 0) == 0 and s.get("score", 0) < 40]
    if not thin_stores:
        return stores

    # Only deep-crawl up to 3 thin stores to stay within free tier
    for store in thin_stores[:3]:
        try:
            from services.tier1_upgrades import firecrawl_scrape
            domain = store.get("domain", "")
            result = await firecrawl_scrape(f"https://{domain}", formats=["markdown"])
            markdown = result.get("markdown", "")
            if not markdown:
                continue

            # Extract emails from crawled content
            import re
            found_emails = list(set(re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', markdown)))
            if found_emails:
                for email in found_emails[:3]:
                    if not any(e.get("email") == email for e in store.get("emails", [])):
                        store.setdefault("emails", []).append({"email": email, "type": "firecrawl", "confidence": 70})
                store["email_count"] = len(store.get("emails", []))

            # Extract phone numbers
            found_phones = list(set(re.findall(r'[\+]?[1-9]\d{1,14}', markdown)))
            found_phones = [p for p in found_phones if len(p) >= 10]
            if found_phones and not store.get("phones"):
                store["phones"] = found_phones[:2]

            # Bump score — reachable via firecrawl means it's a real site
            if store.get("score", 0) < 25:
                store["score"] = max(store.get("score", 0), 25)

            store["corrective_enriched"] = True
            logger.info(f"[FORENSIC MINER] Corrective enrichment: {domain} → {len(found_emails)} emails found")
        except Exception as e:
            logger.debug(f"[FORENSIC MINER] Corrective enrichment failed for {store.get('domain')}: {e}")

    return stores


async def scan_niche(
    niche: str,
    limit: int = 10,
    zone: str = "com",
    auto_outreach: bool = False,
    tenant_id: str = "aurem_platform",
) -> Dict:
    """
    Master Forensic Miner scan — full pipeline:
    1. Search domains by niche
    2. Find emails + contacts
    3. Health scan each store
    4. Queue outreach if enabled
    """
    scan_id = f"scan_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc).isoformat()
    keywords = NICHE_KEYWORDS.get(niche, [niche])

    # Phase 1: Domain discovery
    all_domains = []
    for kw in keywords[:3]:
        domains = await _search_domains(kw, zone, limit=limit)
        all_domains.extend(domains)
        await asyncio.sleep(0.3)

    # Deduplicate
    seen = set()
    unique_domains = []
    for d in all_domains:
        dom = d.get("domain", "")
        if dom and dom not in seen:
            seen.add(dom)
            unique_domains.append(d)
    unique_domains = unique_domains[:limit]

    # Phase 2: Enrich each domain (parallel with concurrency limit)
    stores = []
    sem = asyncio.Semaphore(3)

    async def enrich(domain_info: dict) -> Dict:
        async with sem:
            dom = domain_info.get("domain", "")
            if not dom:
                return None

            # Parallel: emails + health + contacts
            email_task = _find_emails(dom)
            health_task = _quick_health_scan(dom)
            contact_task = _extract_contacts(dom)

            email_data, health_data, contact_data = await asyncio.gather(
                email_task, health_task, contact_task, return_exceptions=True,
            )

            if isinstance(email_data, Exception):
                email_data = {"domain": dom, "emails": [], "total_found": 0}
            if isinstance(health_data, Exception):
                health_data = {"domain": dom, "score": 0, "reachable": False}
            if isinstance(contact_data, Exception):
                contact_data = {"emails_from_site": [], "phones": [], "social": {}}

            # Merge all emails (Tomba + site scrape)
            all_emails = email_data.get("emails", [])
            site_emails = contact_data.get("emails_from_site", [])
            for se in site_emails:
                if not any(e.get("email") == se for e in all_emails):
                    all_emails.append({"email": se, "type": "site_scrape", "confidence": 50})

            return {
                "domain": dom,
                "created": domain_info.get("create_date", ""),
                "organization": email_data.get("organization", ""),
                "emails": all_emails[:5],
                "email_count": len(all_emails),
                "phones": contact_data.get("phones", [])[:3],
                "social": contact_data.get("social", {}),
                "health": health_data,
                "score": health_data.get("score", 0),
                "issues": health_data.get("issues", []),
            }

    tasks = [enrich(d) for d in unique_domains]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    stores = [r for r in results if isinstance(r, dict)]

    # Phase 2.5: CORRECTIVE RAG — Firecrawl deep-crawl thin results
    # (Inspired by firecrawl-agent: retrieve → grade relevance → web-search fallback)
    stores = await _corrective_enrich(stores)

    # Sort by health score (worst first — most fixable = best leads)
    stores.sort(key=lambda s: s.get("score", 0))

    # Phase 3: Queue outreach (if enabled)
    outreach_queued = 0
    if auto_outreach:
        for store in stores:
            if store.get("emails"):
                try:
                    db = _get_db()
                    if db:
                        await db.forensic_miner_outreach_queue.insert_one({
                            "scan_id": scan_id,
                            "domain": store["domain"],
                            "email": store["emails"][0].get("email", ""),
                            "health_score": store.get("score", 0),
                            "issues": store.get("issues", []),
                            "status": "queued",
                            "channels": ["email", "whatsapp"] if store.get("phones") else ["email"],
                            "created_at": now,
                        })
                        outreach_queued += 1
                except Exception:
                    pass

    # Save scan report
    db = _get_db()
    report = {
        "scan_id": scan_id,
        "tenant_id": tenant_id,
        "niche": niche,
        "zone": zone,
        "keywords_used": keywords[:3],
        "domains_found": len(unique_domains),
        "stores_enriched": len(stores),
        "emails_found": sum(s.get("email_count", 0) for s in stores),
        "avg_health_score": round(sum(s.get("score", 0) for s in stores) / max(1, len(stores)), 1),
        "outreach_queued": outreach_queued,
        "stores": stores,
        "created_at": now,
    }
    if db:
        await db.forensic_miner_scans.insert_one({k: v for k, v in report.items() if k != "stores"})

    return report


async def get_scan_history(tenant_id: str = None, limit: int = 10) -> List[Dict]:
    db = _get_db()
    if not db:
        return []
    q = {"tenant_id": tenant_id} if tenant_id else {}
    return await db.forensic_miner_scans.find(q, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
