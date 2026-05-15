"""
AUREM Tier 1 Upgrades Router
POST /api/tier1/tavily/search — AI-optimized search
POST /api/tier1/tavily/extract — extract URLs
POST /api/tier1/firecrawl/scrape — URL → clean markdown
POST /api/tier1/firecrawl/crawl — crawl entire site
POST /api/tier1/vanna/query — natural language → DB results
GET  /api/tier1/brand/guidelines — get brand guidelines
GET  /api/tier1/brand/all — all 3 brands
POST /api/tier1/brand/enforce — check text against brand
POST /api/tier1/report/generate — generate XLSX report
GET  /api/tier1/report/download/{report_id} — download report
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(prefix="/api/tier1", tags=["Tier 1 Upgrades"])
logger = logging.getLogger(__name__)


async def _auth(authorization: str = Header(None)):
    """Bug-fix #152 (R18): require an admin claim, not just a valid JWT.
    Previously any signed JWT was accepted — letting a customer-tier
    token run Vanna queries / Tavily / Firecrawl with admin-tier quota.
    """
    from utils.admin_guard import verify_admin
    return verify_admin(authorization)


def _tenant(p: dict) -> str:
    return p.get("tenant_id") or p.get("business_id") or "aurem_platform"


def _init():
    from services.tier1_upgrades import set_db
    try:
        import server
        if hasattr(server, "db"):
            set_db(server.db)
    except Exception:
        pass


# ═══ TAVILY SEARCH ═══

class TavilySearchRequest(BaseModel):
    query: str
    max_results: int = 5
    search_depth: str = "basic"
    include_answer: bool = True


@router.post("/tavily/search")
async def tavily_search(req: TavilySearchRequest, authorization: str = Header(None)):
    """AI-optimized search. Falls back to DuckDuckGo if no key."""
    await _auth(authorization)
    from services.tier1_upgrades import tavily_search as _search
    return await _search(req.query, req.max_results, req.search_depth, req.include_answer)


class TavilyExtractRequest(BaseModel):
    urls: List[str]


@router.post("/tavily/extract")
async def tavily_extract(req: TavilyExtractRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.tier1_upgrades import tavily_extract as _extract
    return await _extract(req.urls)


# ═══ FIRECRAWL ═══

class FirecrawlScrapeRequest(BaseModel):
    url: str
    formats: List[str] = ["markdown"]


@router.post("/firecrawl/scrape")
async def firecrawl_scrape(req: FirecrawlScrapeRequest, authorization: str = Header(None)):
    """Scrape any URL into clean markdown. Falls back to web_fetch."""
    await _auth(authorization)
    from services.tier1_upgrades import firecrawl_scrape as _scrape
    return await _scrape(req.url, req.formats)


class FirecrawlCrawlRequest(BaseModel):
    url: str
    limit: int = 10


@router.post("/firecrawl/crawl")
async def firecrawl_crawl(req: FirecrawlCrawlRequest, authorization: str = Header(None)):
    await _auth(authorization)
    from services.tier1_upgrades import firecrawl_crawl as _crawl
    return await _crawl(req.url, req.limit)


# ═══ VANNA AI ═══

class VannaQueryRequest(BaseModel):
    question: str


@router.post("/vanna/query")
async def vanna_query(req: VannaQueryRequest, authorization: str = Header(None)):
    """Ask a question in plain English → get MongoDB results."""
    p = await _auth(authorization)
    _init()
    from services.tier1_upgrades import natural_language_query
    return await natural_language_query(req.question, _tenant(p))


# ═══ BRAND GUIDELINES ═══

@router.get("/brand/guidelines")
async def brand_guidelines(brand: str = "aurem", authorization: str = Header(None)):
    await _auth(authorization)
    from services.tier1_upgrades import get_brand_guidelines
    return get_brand_guidelines(brand)


@router.get("/brand/all")
async def all_brands(authorization: str = Header(None)):
    await _auth(authorization)
    from services.tier1_upgrades import get_all_brands
    return get_all_brands()


class BrandEnforceRequest(BaseModel):
    text: str
    brand: str = "aurem"


@router.post("/brand/enforce")
async def brand_enforce(req: BrandEnforceRequest, authorization: str = Header(None)):
    """Check text against brand guidelines. Returns violations + fixes."""
    await _auth(authorization)
    from services.tier1_upgrades import enforce_brand
    return await enforce_brand(req.text, req.brand)


# ═══ XLSX REPORTS ═══

class ReportRequest(BaseModel):
    report_type: str = "monthly_performance"


@router.post("/report/generate")
async def generate_report(req: ReportRequest, authorization: str = Header(None)):
    """Generate Excel performance report."""
    p = await _auth(authorization)
    _init()
    from services.tier1_upgrades import generate_xlsx_report
    return await generate_xlsx_report(_tenant(p), req.report_type)


@router.get("/report/download/{report_id}")
async def download_report(report_id: str, authorization: str = Header(None)):
    """Download generated XLSX report."""
    await _auth(authorization)
    fpath = f"/app/backend/uploads/reports/{report_id}.xlsx"
    if not os.path.exists(fpath):
        raise HTTPException(404, "Report not found")
    return FileResponse(fpath, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=f"{report_id}.xlsx")


# ═══ CANVAS DESIGN ═══

class CanvasRequest(BaseModel):
    headline: str
    subtext: str = ""
    brand: str = "aurem"
    template: str = "linkedin_banner"
    style: str = "minimal"


@router.post("/canvas/generate")
async def canvas_generate(req: CanvasRequest, authorization: str = Header(None)):
    """Generate social graphic (HTML/CSS → PNG). Text in → PNG out."""
    await _auth(authorization)
    _init()
    from services.tier1_upgrades import generate_canvas_design
    return await generate_canvas_design(req.headline, req.subtext, req.brand, req.template, req.style)


@router.get("/canvas/templates")
async def canvas_templates(authorization: str = Header(None)):
    """List available canvas templates and sizes."""
    await _auth(authorization)
    from services.tier1_upgrades import get_canvas_templates
    return {"templates": get_canvas_templates()}


@router.get("/canvas/download/{canvas_id}")
async def canvas_download(canvas_id: str, authorization: str = Header(None)):
    """Download generated PNG canvas."""
    await _auth(authorization)
    png_path = f"/app/backend/uploads/canvas/{canvas_id}.png"
    if os.path.exists(png_path):
        return FileResponse(png_path, media_type="image/png", filename=f"{canvas_id}.png")
    html_path = f"/app/backend/uploads/canvas/{canvas_id}.html"
    if os.path.exists(html_path):
        return FileResponse(html_path, media_type="text/html", filename=f"{canvas_id}.html")
    raise HTTPException(404, "Canvas not found")
