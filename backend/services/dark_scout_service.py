"""
AUREM Dark Scout Service — Intelligence Layer 3
Adapted from Robin OSINT tool (github.com/apurvsinghgautam/robin)
Uses Camofox as primary scraping engine (Tor-optional for Legion workstation).

Capabilities:
  - Brand/client data breach monitoring (surface + dark web)
  - Competitor intelligence gathering
  - Threat landscape scanning
  - LLM-powered noise filtering & analysis
  - OODA loop integration (triggered by Sentinel anomalies)

Architecture: Search → Scrape → Filter (LLM) → Analyze (LLM) → Store → Alert
"""
import logging
import os
import re
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

_db = None


def set_db(db):
    global _db
    _db = db


def _get_db():
    global _db
    if _db is not None:
        return _db
    try:
        import server
        if hasattr(server, "db") and server.db is not None:
            _db = server.db
            return _db
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════
# SEARCH ENGINES (Surface Web — Camofox-powered)
# ══════════════════════════════════════════════

SURFACE_SEARCH_ENGINES = [
    {"name": "Google", "url": "https://www.google.com/search?q={query}&num=20"},
    {"name": "DuckDuckGo", "url": "https://html.duckduckgo.com/html/?q={query}"},
    {"name": "Bing", "url": "https://www.bing.com/search?q={query}&count=20"},
]

# Dark web search engines (require Tor — disabled by default, enabled on Legion)
DARK_SEARCH_ENGINES = [
    {"name": "Ahmia", "url": "http://juhanurmihxlp77nkq76byazcldy2hlmovfu2epvl5ankdibsot4csyd.onion/search/?q={query}"},
    {"name": "Torch", "url": "http://torchdeedp3i2jigzjdmfpn5ttjhthh5wbmda2rr3jvqber7srctcead.onion/search?query={query}"},
    {"name": "Torgle", "url": "http://iy3544gmoeclh5de6gez2256v6pjh4omhpqdh2wpeeppjtvqmjhkfwad.onion/torgle/?query={query}"},
]

# Analysis presets (adapted from Robin's llm.py)
ANALYSIS_PRESETS = {
    "brand_monitor": (
        "You are a Brand Protection Intelligence Expert. Analyze the data for:\n"
        "1. Any mentions of the brand, company name, or key personnel\n"
        "2. Leaked credentials, customer data, or internal documents\n"
        "3. Fake websites, phishing pages, or impersonation attempts\n"
        "4. Negative sentiment or reputation threats\n"
        "5. Competitor mentions in the same context\n\n"
        "Output: Risk Level (LOW/MEDIUM/HIGH/CRITICAL), Key Findings, Evidence Links, Recommended Actions.\n"
        "Be concise and actionable. Focus on business impact.\n\nINPUT:\n"
    ),
    "competitor_intel": (
        "You are a Competitive Intelligence Expert. Analyze the data for:\n"
        "1. Competitor pricing changes, new products, or service updates\n"
        "2. Customer complaints or satisfaction signals about competitors\n"
        "3. Technology stack or infrastructure changes\n"
        "4. Hiring patterns indicating strategic direction\n"
        "5. Partnership or acquisition signals\n\n"
        "Output: Key Insights (3-5), Competitive Threats, Opportunities, Recommended Actions.\n\nINPUT:\n"
    ),
    "breach_detection": (
        "You are a Data Breach Intelligence Expert. Analyze the data for:\n"
        "1. Leaked credentials (emails, passwords, API keys)\n"
        "2. Database dumps containing customer or employee PII\n"
        "3. Source code or internal documentation exposure\n"
        "4. Financial data or payment information leaks\n"
        "5. Threat actors discussing or selling the data\n\n"
        "Output: Severity (LOW/MEDIUM/HIGH/CRITICAL), Exposed Data Types, Source Links, Immediate Actions Required.\n\nINPUT:\n"
    ),
    "threat_landscape": (
        "You are a Cybercrime Threat Intelligence Expert. Analyze the data for:\n"
        "1. Active threats targeting the industry or geography\n"
        "2. New attack vectors, malware families, or exploit kits\n"
        "3. Threat actor profiles and their targeting patterns\n"
        "4. Vulnerability discussions relevant to the target's tech stack\n"
        "5. Emerging risks in the next 30-90 days\n\n"
        "Output: Threat Level, Key Threats (3-5), Indicators of Compromise, Recommended Defenses.\n\nINPUT:\n"
    ),
}


# ══════════════════════════════════════════════
# CORE: Search (via Camofox or httpx)
# ══════════════════════════════════════════════

async def _search_engine(engine: dict, query: str) -> list:
    """Search a single engine and extract result links."""
    url = engine["url"].format(query=quote_plus(query))
    results = []

    try:
        from services.camofox_client import browse_url
        data = await browse_url(url)
        text = data.get("text", "")
        links = data.get("links", [])

        # Extract meaningful links from page
        for link in links:
            href = link if isinstance(link, str) else link.get("href", "")
            title = link.get("text", "") if isinstance(link, dict) else ""
            if href and not any(skip in href for skip in ["google.com/search", "bing.com/search", "duckduckgo.com", "javascript:"]):
                results.append({"title": title or href[:60], "link": href, "source": engine["name"]})
    except Exception as e:
        logger.debug(f"[DarkScout] Search engine {engine['name']} failed: {e}")

    return results


async def search_surface(query: str, max_results: int = 30) -> list:
    """Search surface web engines concurrently via Camofox."""
    tasks = [_search_engine(eng, query) for eng in SURFACE_SEARCH_ENGINES]
    all_results = await asyncio.gather(*tasks, return_exceptions=True)

    combined = []
    seen = set()
    for result_set in all_results:
        if isinstance(result_set, Exception):
            continue
        for r in result_set:
            clean_link = r["link"].rstrip("/")
            if clean_link not in seen:
                seen.add(clean_link)
                combined.append(r)

    return combined[:max_results]


# ══════════════════════════════════════════════
# CORE: Scrape (via Camofox with resilient fetch)
# ══════════════════════════════════════════════

async def scrape_urls(urls: list, max_concurrent: int = 5) -> dict:
    """Scrape multiple URLs concurrently. Returns {url: extracted_text}."""
    results = {}
    sem = asyncio.Semaphore(max_concurrent)

    async def _scrape_one(url_data):
        url = url_data.get("link", "") if isinstance(url_data, dict) else str(url_data)
        if not url:
            return
        async with sem:
            try:
                from utils.resilient_fetch import resilient_fetch
                result = await resilient_fetch(url, timeout=20.0)
                if result.success:
                    text = result.text
                    # Clean HTML to text
                    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.S)
                    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.S)
                    text = re.sub(r'<[^>]+>', ' ', text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    results[url] = text[:2000]  # Cap at 2000 chars per page
            except Exception as e:
                logger.debug(f"[DarkScout] Scrape failed for {url[:60]}: {e}")

    tasks = [_scrape_one(u) for u in urls[:max_concurrent * 3]]
    await asyncio.gather(*tasks)
    return results


# ══════════════════════════════════════════════
# CORE: LLM Filter & Analyze (via Emergent LLM)
# ══════════════════════════════════════════════

async def filter_results_llm(query: str, results: list) -> list:
    """Use LLM to filter top relevant results from search output."""
    if not results:
        return []

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        llm_key = os.environ.get("EMERGENT_LLM_KEY")
        if not llm_key:
            return results[:20]

        # Format results for LLM
        formatted = "\n".join(f"{i+1}. {r.get('link','')} - {r.get('title','')}" for i, r in enumerate(results[:50]))

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"darkscout-filter-{uuid.uuid4().hex[:8]}",
            system_message="You are a search-result relevance filter. Reply with comma-separated indices only.",
        ).with_model("openai", "gpt-4o-mini")
        resp_text = await chat.send_message(UserMessage(text=(
            f"Search query: {query}\n\n"
            f"Results:\n{formatted}\n\n"
            "Select the top 15 most relevant result indices (comma-separated numbers only). "
            "Focus on results that contain actual intelligence value, not ads or generic pages."
        )))

        # Parse indices
        indices = []
        for match in re.findall(r"\d+", resp_text or ""):
            idx = int(match)
            if 1 <= idx <= len(results):
                indices.append(idx - 1)

        if indices:
            return [results[i] for i in dict.fromkeys(indices)][:15]
    except Exception as e:
        logger.warning(f"[DarkScout] LLM filter failed: {e}")

    return results[:15]


async def analyze_intelligence(query: str, scraped_data: dict, preset: str = "brand_monitor") -> dict:
    """LLM-powered analysis of scraped intelligence data."""
    if not scraped_data:
        return {"analysis": "No data to analyze", "risk_level": "LOW", "findings": []}

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        llm_key = os.environ.get("EMERGENT_LLM_KEY")
        if not llm_key:
            return {"analysis": "LLM key not available", "risk_level": "UNKNOWN", "findings": []}

        # Prepare content
        content_parts = []
        for url, text in list(scraped_data.items())[:10]:
            content_parts.append(f"URL: {url}\nContent: {text[:500]}\n---")
        content = "\n".join(content_parts)

        system_prompt = ANALYSIS_PRESETS.get(preset, ANALYSIS_PRESETS["brand_monitor"])

        chat = LlmChat(
            api_key=llm_key,
            session_id=f"darkscout-analyze-{uuid.uuid4().hex[:8]}",
            system_message=system_prompt,
        ).with_model("openai", "gpt-4o-mini")
        resp_text = await chat.send_message(UserMessage(text=f"Query: {query}\n\nData:\n{content}"))

        # Parse risk level from response
        risk = "LOW"
        text_upper = (resp_text or "").upper()
        if "CRITICAL" in text_upper:
            risk = "CRITICAL"
        elif "HIGH" in text_upper:
            risk = "HIGH"
        elif "MEDIUM" in text_upper:
            risk = "MEDIUM"

        return {
            "analysis": resp_text or "",
            "risk_level": risk,
            "sources_analyzed": len(scraped_data),
            "findings": [],
        }
    except Exception as e:
        logger.warning(f"[DarkScout] LLM analysis failed: {e}")
        return {"analysis": f"Analysis failed: {e}", "risk_level": "UNKNOWN", "findings": []}


# ══════════════════════════════════════════════
# MAIN: Run Dark Scout Investigation
# ══════════════════════════════════════════════

async def run_investigation(
    query: str,
    tenant_id: str = "system",
    preset: str = "brand_monitor",
    max_results: int = 15,
) -> dict:
    """
    Full Dark Scout pipeline: Search → Scrape → Filter → Analyze → Store.
    This is the main entry point called by OODA loop or manual trigger.
    """
    db = _get_db()
    investigation_id = f"inv-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc)

    logger.info(f"[DarkScout] Starting investigation: {query} (preset={preset})")

    result = {
        "investigation_id": investigation_id,
        "query": query,
        "tenant_id": tenant_id,
        "preset": preset,
        "status": "running",
        "started_at": now.isoformat(),
        "completed_at": None,
        "search_results": 0,
        "filtered_results": 0,
        "scraped_pages": 0,
        "risk_level": "UNKNOWN",
        "analysis": "",
        "sources": [],
        "error": "",
    }

    try:
        # Step 1: Search
        raw_results = await search_surface(query, max_results=50)
        result["search_results"] = len(raw_results)
        logger.info(f"[DarkScout] Search returned {len(raw_results)} results")

        if not raw_results:
            result["status"] = "completed"
            result["risk_level"] = "LOW"
            result["analysis"] = "No results found for this query."
            result["completed_at"] = datetime.now(timezone.utc).isoformat()
            if db:
                await db.dark_scout_investigations.insert_one({k: v for k, v in result.items()})
            return result

        # Step 2: LLM Filter (reduce noise)
        filtered = await filter_results_llm(query, raw_results)
        result["filtered_results"] = len(filtered)
        result["sources"] = [{"title": r.get("title", ""), "link": r.get("link", ""), "source": r.get("source", "")} for r in filtered]
        logger.info(f"[DarkScout] Filtered to {len(filtered)} relevant results")

        # Step 3: Scrape top results
        scraped = await scrape_urls(filtered[:max_results], max_concurrent=5)
        result["scraped_pages"] = len(scraped)
        logger.info(f"[DarkScout] Scraped {len(scraped)} pages")

        # Step 4: LLM Analysis
        analysis = await analyze_intelligence(query, scraped, preset=preset)
        result["analysis"] = analysis.get("analysis", "")
        result["risk_level"] = analysis.get("risk_level", "LOW")

        result["status"] = "completed"
        result["completed_at"] = datetime.now(timezone.utc).isoformat()

    except Exception as e:
        logger.error(f"[DarkScout] Investigation failed: {e}")
        result["status"] = "failed"
        result["error"] = str(e)
        result["completed_at"] = datetime.now(timezone.utc).isoformat()

    # Store in DB
    if db:
        try:
            await db.dark_scout_investigations.insert_one({k: v for k, v in result.items()})
        except Exception as e:
            logger.warning(f"[DarkScout] DB store failed: {e}")

    # Log to Agent Observatory
    try:
        from routers.agent_observatory_router import log_trace
        await log_trace(
            tenant_id=tenant_id,
            session_id=investigation_id,
            agent="Dark Scout",
            action=f"investigation_{preset}",
            steps=[
                {"step_number": 1, "agent": "Scout", "action": "search_surface", "tool_called": "camofox", "input_summary": query, "output_summary": f"{result['search_results']} results", "duration_ms": 0, "status": "success", "error": ""},
                {"step_number": 2, "agent": "Filter", "action": "llm_filter", "tool_called": "gpt-4o-mini", "input_summary": f"{result['search_results']} raw", "output_summary": f"{result['filtered_results']} filtered", "duration_ms": 0, "status": "success", "error": ""},
                {"step_number": 3, "agent": "Scraper", "action": "scrape_urls", "tool_called": "resilient_fetch", "input_summary": f"{result['filtered_results']} urls", "output_summary": f"{result['scraped_pages']} scraped", "duration_ms": 0, "status": "success", "error": ""},
                {"step_number": 4, "agent": "Analyst", "action": "analyze_intelligence", "tool_called": "gpt-4o-mini", "input_summary": f"{result['scraped_pages']} pages", "output_summary": f"Risk: {result['risk_level']}", "duration_ms": 0, "status": "success" if result["status"] == "completed" else "failed", "error": result.get("error", "")},
            ],
            total_duration_ms=0,
            status=result["status"],
            tools_used=["camofox", "resilient_fetch", "gpt-4o-mini"],
            llm_calls=2,
        )
    except Exception:
        pass

    return result


# ══════════════════════════════════════════════
# OODA Loop Trigger — called by Sentinel on anomaly
# ══════════════════════════════════════════════

async def sentinel_trigger(tenant_id: str, anomaly_type: str, details: str):
    """
    Triggered automatically by Sentinel Healer when a security anomaly is detected.
    Runs a Dark Scout investigation based on the anomaly context.
    """
    query_map = {
        "data_breach": f'"{details}" data breach leak',
        "credential_leak": f'"{details}" credentials dump password',
        "brand_impersonation": f'"{details}" fake phishing scam',
        "security_anomaly": f'"{details}" vulnerability exploit',
    }
    query = query_map.get(anomaly_type, f'"{details}" security threat')
    preset = "breach_detection" if "breach" in anomaly_type or "credential" in anomaly_type else "brand_monitor"

    logger.info(f"[DarkScout] Sentinel trigger: {anomaly_type} for {tenant_id}")
    return await run_investigation(query=query, tenant_id=tenant_id, preset=preset)
