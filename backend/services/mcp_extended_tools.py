"""
AUREM MCP Extended Tools — Web Browse + File System + Database
==============================================================
Three new MCP tool groups extending the existing /api/mcp/* infrastructure:
  1. Web Browse MCP — HTTP crawl + extract for Forensic Miner
  2. File System MCP — Read/write repair deployment files
  3. Database MCP — Direct MongoDB query/aggregate access for agents
"""
import os
import re
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

import httpx
from bs4 import BeautifulSoup

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
            return _db
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════════
# 1. WEB BROWSE MCP — Forensic Miner crawling
# ═══════════════════════════════════════════════════════════════

TOOL_DEFS_WEB = [
    {"name": "web_fetch", "description": "Fetch a URL and return clean text + metadata (title, meta, links, images). For Forensic Miner site analysis.",
     "parameters": {"url": "Target URL to crawl", "extract": "What to extract: text|links|images|meta|all (default: all)", "max_chars": "Max text characters (default: 5000)"}},
    {"name": "web_search", "description": "Search DuckDuckGo for results. Returns titles + URLs + snippets.",
     "parameters": {"query": "Search query", "limit": "Max results (default: 5)"}},
    {"name": "web_extract_contacts", "description": "Extract emails, phone numbers, and social links from a URL.",
     "parameters": {"url": "Target URL to scan for contacts"}},
]


async def web_fetch(url: str, extract: str = "all", max_chars: int = 5000) -> Dict:
    """Fetch URL, parse HTML, return structured data."""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "AUREM-ForensicMiner/1.0"})
            if resp.status_code != 200:
                return {"error": f"HTTP {resp.status_code}", "url": url}
            html = resp.text
    except Exception as e:
        return {"error": str(e), "url": url}

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    result = {"url": url, "status": 200}

    if extract in ("meta", "all"):
        title_tag = soup.find("title")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        og_title = soup.find("meta", property="og:title")
        og_image = soup.find("meta", property="og:image")
        result["meta"] = {
            "title": title_tag.string.strip() if title_tag and title_tag.string else "",
            "description": meta_desc.get("content", "").strip() if meta_desc else "",
            "og_title": og_title.get("content", "") if og_title else "",
            "og_image": og_image.get("content", "") if og_image else "",
        }

    if extract in ("text", "all"):
        text = soup.get_text(separator="\n", strip=True)
        result["text"] = text[:max_chars]
        result["text_length"] = len(text)

    if extract in ("links", "all"):
        from urllib.parse import urlparse, urljoin
        domain = urlparse(url).netloc
        links = []
        for a in soup.find_all("a", href=True)[:50]:
            href = urljoin(url, a["href"])
            is_external = urlparse(href).netloc != domain
            links.append({"text": a.get_text(strip=True)[:80], "href": href, "external": is_external})
        result["links"] = links
        result["link_count"] = len(links)

    if extract in ("images", "all"):
        images = []
        for img in soup.find_all("img", src=True)[:30]:
            from urllib.parse import urljoin as uj
            images.append({"src": uj(url, img["src"]), "alt": img.get("alt", ""), "has_alt": bool(img.get("alt"))})
        result["images"] = images
        result["images_without_alt"] = sum(1 for i in images if not i["has_alt"])

    return result


async def web_search(query: str, limit: int = 5) -> Dict:
    """Search via DuckDuckGo text search."""
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        results = list(ddgs.text(query, max_results=limit))
        return {"query": query, "results": [{"title": r.get("title", ""), "url": r.get("href", ""), "snippet": r.get("body", "")[:200]} for r in results], "count": len(results)}
    except Exception as e:
        return {"query": query, "error": str(e), "results": []}


async def web_extract_contacts(url: str) -> Dict:
    """Extract emails, phones, social links from a URL."""
    fetch_result = await web_fetch(url, extract="text")
    if fetch_result.get("error"):
        return fetch_result

    text = fetch_result.get("text", "")
    emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)))
    phones = list(set(re.findall(r'[\+]?[(]?[0-9]{1,4}[)]?[-\s\./0-9]{7,15}', text)))
    phones = [p.strip() for p in phones if len(p.strip()) >= 10]

    # Social links from full HTML
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            resp = await client.get(url if url.startswith("http") else f"https://{url}", headers={"User-Agent": "AUREM-ForensicMiner/1.0"})
            html = resp.text
        except Exception:
            html = ""

    social = {}
    patterns = {"instagram": r'instagram\.com/([a-zA-Z0-9_.]+)', "twitter": r'(?:twitter|x)\.com/([a-zA-Z0-9_]+)',
                "linkedin": r'linkedin\.com/(?:in|company)/([a-zA-Z0-9_-]+)', "facebook": r'facebook\.com/([a-zA-Z0-9._]+)',
                "youtube": r'youtube\.com/(?:@|channel/|c/)([a-zA-Z0-9_-]+)', "tiktok": r'tiktok\.com/@([a-zA-Z0-9_.]+)'}
    for platform, pattern in patterns.items():
        match = re.search(pattern, html)
        if match:
            social[platform] = match.group(1)

    return {"url": url, "emails": emails[:10], "phones": phones[:10], "social": social, "email_count": len(emails), "phone_count": len(phones)}


# ═══════════════════════════════════════════════════════════════
# 2. FILE SYSTEM MCP — Repair deployment files
# ═══════════════════════════════════════════════════════════════

TOOL_DEFS_FS = [
    {"name": "fs_list_repairs", "description": "List repair deployment files (patches, CSS, HTML) for a scanned URL.",
     "parameters": {"url": "Scanned URL to list repairs for", "status": "Filter: pending_approval|approved|deployed|all (default: all)"}},
    {"name": "fs_read_patch", "description": "Read the HTML/CSS patch content for a specific deployment.",
     "parameters": {"deploy_id": "Deployment ID to read"}},
    {"name": "fs_write_patch", "description": "Write/update a custom patch file for manual deployment.",
     "parameters": {"deploy_id": "Deployment ID", "content": "Patch file content (HTML/CSS)", "filename": "Output filename"}},
    {"name": "fs_list_templates", "description": "List available email templates.",
     "parameters": {}},
]

PATCH_DIR = "/app/backend/uploads/patches"


async def fs_list_repairs(url: str = None, status: str = "all") -> Dict:
    db = _get_db()
    if db is None:
        return {"error": "no_db"}
    query = {}
    if url:
        query["scan_url"] = url
    if status != "all":
        query["status"] = status
    fixes = await db.repair_fixes.find(query, {"_id": 0, "fix_id": 1, "fix_type": 1, "label": 1, "category": 1, "status": 1, "scan_url": 1, "created_at": 1}).sort("created_at", -1).to_list(100)
    return {"fixes": fixes, "count": len(fixes)}


async def fs_read_patch(deploy_id: str) -> Dict:
    db = _get_db()
    if db is None:
        return {"error": "no_db"}
    deploy = await db.repair_deployments.find_one({"deploy_id": deploy_id}, {"_id": 0, "html_patch": 1, "diffs": 1, "scan_url": 1, "fix_count": 1, "status": 1})
    if not deploy:
        return {"error": "Deployment not found"}
    return {"deploy_id": deploy_id, "scan_url": deploy.get("scan_url"), "status": deploy.get("status"), "fix_count": deploy.get("fix_count"), "patch_content": deploy.get("html_patch", ""), "diffs": deploy.get("diffs", [])}


async def fs_write_patch(deploy_id: str, content: str, filename: str = None) -> Dict:
    os.makedirs(PATCH_DIR, exist_ok=True)
    fname = filename or f"patch-{deploy_id}.html"
    fpath = os.path.join(PATCH_DIR, fname)
    try:
        with open(fpath, "w") as f:
            f.write(content)
        return {"success": True, "path": fpath, "size": len(content), "filename": fname}
    except Exception as e:
        return {"error": str(e)}


async def fs_list_templates() -> Dict:
    template_dir = "/app/backend/templates"
    if not os.path.isdir(template_dir):
        return {"templates": [], "count": 0}
    files = [f for f in os.listdir(template_dir) if f.endswith((".html", ".txt"))]
    return {"templates": files, "count": len(files), "directory": template_dir}


# ═══════════════════════════════════════════════════════════════
# 3. DATABASE MCP — Direct MongoDB access for agents
# ═══════════════════════════════════════════════════════════════

TOOL_DEFS_DB = [
    {"name": "db_query", "description": "Query any MongoDB collection with filters. Returns documents (max 50). Read-only — safe for agents.",
     "parameters": {"collection": "Collection name (e.g. tenant_customers, leads, invoices)", "filter": "MongoDB filter as JSON (default: {})", "projection": "Fields to return as JSON (default: excludes _id)", "sort": "Sort field (default: -timestamp)", "limit": "Max results (default: 20, max: 50)"}},
    {"name": "db_aggregate", "description": "Run a MongoDB aggregation pipeline. For complex analytics queries.",
     "parameters": {"collection": "Collection name", "pipeline": "Aggregation pipeline as JSON array"}},
    {"name": "db_count", "description": "Count documents matching a filter.",
     "parameters": {"collection": "Collection name", "filter": "MongoDB filter as JSON (default: {})"}},
    {"name": "db_collections", "description": "List all MongoDB collections with document counts.",
     "parameters": {}},
    {"name": "db_sample", "description": "Get a random sample document from a collection (useful to understand schema).",
     "parameters": {"collection": "Collection name"}},
]

# Blocklist — never expose these collections to MCP
_BLOCKED_COLLECTIONS = {"users", "nexus_credentials", "api_keys", "github_connections", "biometric_credentials", "session_keys", "jwt_blocklist"}


def _sanitize_collection(name: str) -> bool:
    return name not in _BLOCKED_COLLECTIONS and not name.startswith("system.")


async def db_query(collection: str, filter_json: str = "{}", projection_json: str = None, sort: str = "-timestamp", limit: int = 20) -> Dict:
    db = _get_db()
    if db is None:
        return {"error": "no_db"}
    if not _sanitize_collection(collection):
        return {"error": f"Collection '{collection}' is restricted"}
    try:
        f = json.loads(filter_json) if isinstance(filter_json, str) else filter_json
    except json.JSONDecodeError:
        return {"error": "Invalid filter JSON"}
    proj = {"_id": 0}
    if projection_json:
        try:
            extra = json.loads(projection_json) if isinstance(projection_json, str) else projection_json
            proj.update(extra)
        except Exception:
            pass
    # Parse sort
    sort_dir = -1 if sort.startswith("-") else 1
    sort_field = sort.lstrip("-")
    limit = min(limit, 50)
    try:
        docs = await db[collection].find(f, proj).sort(sort_field, sort_dir).limit(limit).to_list(limit)
        return {"collection": collection, "count": len(docs), "documents": docs}
    except Exception as e:
        return {"error": str(e), "collection": collection}


async def db_aggregate(collection: str, pipeline_json: str = "[]") -> Dict:
    db = _get_db()
    if db is None:
        return {"error": "no_db"}
    if not _sanitize_collection(collection):
        return {"error": f"Collection '{collection}' is restricted"}
    try:
        pipeline = json.loads(pipeline_json) if isinstance(pipeline_json, str) else pipeline_json
    except json.JSONDecodeError:
        return {"error": "Invalid pipeline JSON"}
    # Safety: inject _id exclusion if $project stage is last
    if pipeline and "$project" in pipeline[-1]:
        pipeline[-1]["$project"]["_id"] = 0
    try:
        results = await db[collection].aggregate(pipeline).to_list(100)
        # Sanitize ObjectIds from aggregation results
        for doc in results:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"]) if doc["_id"] else None
        return {"collection": collection, "count": len(results), "results": results}
    except Exception as e:
        return {"error": str(e), "collection": collection}


async def db_count(collection: str, filter_json: str = "{}") -> Dict:
    db = _get_db()
    if db is None:
        return {"error": "no_db"}
    if not _sanitize_collection(collection):
        return {"error": f"Collection '{collection}' is restricted"}
    try:
        f = json.loads(filter_json) if isinstance(filter_json, str) else filter_json
        count = await db[collection].count_documents(f)
        return {"collection": collection, "count": count}
    except Exception as e:
        return {"error": str(e)}


async def db_collections() -> Dict:
    db = _get_db()
    if db is None:
        return {"error": "no_db"}
    try:
        names = await db.list_collection_names()
        safe_names = [n for n in sorted(names) if _sanitize_collection(n)]
        counts = {}
        for n in safe_names[:60]:
            try:
                counts[n] = await db[n].estimated_document_count()
            except Exception:
                counts[n] = -1
        return {"collections": [{"name": n, "documents": counts.get(n, 0)} for n in safe_names], "total": len(safe_names)}
    except Exception as e:
        return {"error": str(e)}


async def db_sample(collection: str) -> Dict:
    db = _get_db()
    if db is None:
        return {"error": "no_db"}
    if not _sanitize_collection(collection):
        return {"error": f"Collection '{collection}' is restricted"}
    try:
        pipeline = [{"$sample": {"size": 1}}, {"$project": {"_id": 0}}]
        docs = await db[collection].aggregate(pipeline).to_list(1)
        if docs:
            return {"collection": collection, "sample": docs[0]}
        return {"collection": collection, "sample": None, "note": "Collection empty"}
    except Exception as e:
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════════
# TOOL REGISTRY — All extended MCP tools
# ═══════════════════════════════════════════════════════════════

ALL_TOOL_DEFS = TOOL_DEFS_WEB + TOOL_DEFS_FS + TOOL_DEFS_DB

# Merge free API tools into MCP
try:
    from services.free_api_arsenal import TOOL_DEFS as FREE_TOOL_DEFS, TOOL_HANDLERS as FREE_HANDLERS
    ALL_TOOL_DEFS = ALL_TOOL_DEFS + FREE_TOOL_DEFS
except Exception:
    FREE_HANDLERS = {}

# Merge Tier 1 upgrade tools
TIER1_TOOL_DEFS = [
    {"name": "tavily_search", "description": "AI-optimized web search via Tavily. Structured results. Replaces DuckDuckGo.", "parameters": {"query": "Search query", "max_results": "Max results (default: 5)"}},
    {"name": "tavily_extract", "description": "Extract clean content from URLs via Tavily.", "parameters": {"urls": "List of URLs to extract"}},
    {"name": "firecrawl_scrape", "description": "Scrape any URL into clean markdown via Firecrawl.", "parameters": {"url": "URL to scrape"}},
    {"name": "firecrawl_crawl", "description": "Crawl entire website. Returns multiple pages as markdown.", "parameters": {"url": "Starting URL", "limit": "Max pages (default: 10)"}},
    {"name": "vanna_query", "description": "Natural language to MongoDB query. Ask a question, get DB results.", "parameters": {"question": "Question in plain English"}},
    {"name": "brand_check", "description": "Check text against AUREM/AURA-GEN/OROE brand guidelines.", "parameters": {"text": "Text to check", "brand": "Brand: aurem, aura_gen, oroe"}},
]
ALL_TOOL_DEFS = ALL_TOOL_DEFS + TIER1_TOOL_DEFS

TOOL_HANDLERS = {
    "web_fetch": lambda args: web_fetch(args.get("url", ""), args.get("extract", "all"), int(args.get("max_chars", 5000))),
    "web_search": lambda args: web_search(args.get("query", ""), int(args.get("limit", 5))),
    "web_extract_contacts": lambda args: web_extract_contacts(args.get("url", "")),
    "fs_list_repairs": lambda args: fs_list_repairs(args.get("url"), args.get("status", "all")),
    "fs_read_patch": lambda args: fs_read_patch(args.get("deploy_id", "")),
    "fs_write_patch": lambda args: fs_write_patch(args.get("deploy_id", ""), args.get("content", ""), args.get("filename")),
    "fs_list_templates": lambda args: fs_list_templates(),
    "db_query": lambda args: db_query(args.get("collection", ""), args.get("filter", "{}"), args.get("projection"), args.get("sort", "-timestamp"), int(args.get("limit", 20))),
    "db_aggregate": lambda args: db_aggregate(args.get("collection", ""), args.get("pipeline", "[]")),
    "db_count": lambda args: db_count(args.get("collection", ""), args.get("filter", "{}")),
    "db_collections": lambda args: db_collections(),
    "db_sample": lambda args: db_sample(args.get("collection", "")),
    **FREE_HANDLERS,
}

# Add Tier 1 handlers
try:
    from services.tier1_upgrades import tavily_search, tavily_extract, firecrawl_scrape, firecrawl_crawl, natural_language_query, enforce_brand
    TOOL_HANDLERS["tavily_search"] = lambda args: tavily_search(args.get("query", ""), int(args.get("max_results", 5)))
    TOOL_HANDLERS["tavily_extract"] = lambda args: tavily_extract(args.get("urls", []))
    TOOL_HANDLERS["firecrawl_scrape"] = lambda args: firecrawl_scrape(args.get("url", ""))
    TOOL_HANDLERS["firecrawl_crawl"] = lambda args: firecrawl_crawl(args.get("url", ""), int(args.get("limit", 10)))
    TOOL_HANDLERS["vanna_query"] = lambda args: natural_language_query(args.get("question", ""))
    TOOL_HANDLERS["brand_check"] = lambda args: enforce_brand(args.get("text", ""), args.get("brand", "aurem"))
except Exception:
    pass


async def call_extended_tool(tool_name: str, arguments: Dict) -> Dict:
    """Dispatch an extended MCP tool call."""
    handler = TOOL_HANDLERS.get(tool_name)
    if not handler:
        return {"error": f"Unknown extended tool: {tool_name}"}
    return await handler(arguments)
