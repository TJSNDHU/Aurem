"""
AUREM Customer Site Audit Service — SEO + Ads Waste Detector ($49/mo upsell).

Pipeline (per audit run):
  1. Google PageSpeed Insights v5 (free Google API key)
       → Lighthouse scores: performance, seo, accessibility, best-practices
       → Core Web Vitals: LCP, FCP, CLS, TBT
  2. Custom Playwright meta-scrape
       → title, meta description, H1 count, OG tags, JSON-LD schema, alt-text gaps
  3. Ads waste heuristics
       → Detects Google Ads / GTM / GA, scores tracking maturity, estimates $/mo waste
       → Heuristic signals: no conversion tracking, no remarketing, slow LCP=>bounced ads,
         generic landing page (no CTA above fold), broad targeting indicators
  4. Persisted to db.customer_audits + db.customer_audit_metrics

Result shape (see CustomerAudit model below) is consumed by /my dashboard widget.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

PSI_BASE_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
PSI_TIMEOUT_S = 60.0


# ─── Models ───────────────────────────────────────────────────────────
class CategoryScores(BaseModel):
    performance: int = 0
    seo: int = 0
    accessibility: int = 0
    best_practices: int = 0


class CoreWebVitals(BaseModel):
    lcp_ms: Optional[float] = None   # Largest Contentful Paint
    fcp_ms: Optional[float] = None   # First Contentful Paint
    cls: Optional[float] = None      # Cumulative Layout Shift
    tbt_ms: Optional[float] = None   # Total Blocking Time


class SeoMetadata(BaseModel):
    title: Optional[str] = None
    title_length: int = 0
    meta_description: Optional[str] = None
    meta_description_length: int = 0
    h1_count: int = 0
    og_image: Optional[str] = None
    has_schema: bool = False
    canonical_url: Optional[str] = None
    img_count: int = 0
    img_alt_missing: int = 0


class AdsAudit(BaseModel):
    has_google_ads: bool = False
    has_gtm: bool = False
    has_ga4: bool = False
    has_conversion_tracking: bool = False
    has_remarketing: bool = False
    cta_above_fold: bool = False
    waste_signals: list[str] = Field(default_factory=list)
    estimated_monthly_waste_usd: int = 0
    confidence: str = "low"  # low|medium|high


class CustomerAudit(BaseModel):
    id: str = Field(default_factory=lambda: f"audit_{uuid.uuid4().hex[:12]}")
    customer_id: str
    bin: Optional[str] = None
    url: str
    strategy: str = "mobile"
    status: str = "pending"  # pending|completed|failed
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    duration_ms: int = 0
    psi_status: str = "ok"   # ok|no_api_key|psi_api_not_enabled|rate_limited|network_error
    scores: CategoryScores = Field(default_factory=CategoryScores)
    core_vitals: CoreWebVitals = Field(default_factory=CoreWebVitals)
    seo: SeoMetadata = Field(default_factory=SeoMetadata)
    ads: AdsAudit = Field(default_factory=AdsAudit)
    top_issues: list[str] = Field(default_factory=list)
    error: Optional[str] = None


# ─── PageSpeed call ───────────────────────────────────────────────────
async def _pagespeed(url: str, strategy: str = "mobile") -> dict:
    """Call Google PageSpeed Insights v5. Returns parsed scores+vitals or
    {} when no key configured or {"_unavailable": "<reason>"} when the API
    is reachable but rejects the call (so the caller can surface a clearer
    message than 0/0/0/0 to the user)."""
    key = (
        os.environ.get("GOOGLE_PSI_API_KEY")
        or os.environ.get("GOOGLE_PAGESPEED_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or ""
    ).strip()
    if not key:
        logger.warning("[audit] GOOGLE_PSI_API_KEY not set — skipping PageSpeed")
        return {"_unavailable": "no_api_key"}

    params = [
        ("url", url),
        ("key", key),
        ("strategy", strategy),
        ("category", "performance"),
        ("category", "seo"),
        ("category", "accessibility"),
        ("category", "best-practices"),
    ]
    try:
        async with httpx.AsyncClient(timeout=PSI_TIMEOUT_S) as c:
            r = await c.get(PSI_BASE_URL, params=params)
            if r.status_code != 200:
                logger.warning(f"[audit] PSI returned {r.status_code} for {url}")
                reason = f"http_{r.status_code}"
                if r.status_code == 403:
                    reason = "psi_api_not_enabled"
                elif r.status_code == 429:
                    reason = "rate_limited"
                return {"_unavailable": reason}
            data = r.json()
    except Exception as e:
        logger.warning(f"[audit] PSI fetch failed for {url}: {e}")
        return {"_unavailable": "network_error"}

    lh = (data or {}).get("lighthouseResult", {}) or {}
    cats = lh.get("categories", {}) or {}
    audits = lh.get("audits", {}) or {}

    def _score(name: str) -> int:
        s = (cats.get(name) or {}).get("score")
        return int(round((s or 0) * 100))

    def _audit_val(name: str) -> Optional[float]:
        return (audits.get(name) or {}).get("numericValue")

    return {
        "scores": {
            "performance": _score("performance"),
            "seo": _score("seo"),
            "accessibility": _score("accessibility"),
            "best_practices": _score("best-practices"),
        },
        "core_vitals": {
            "lcp_ms": _audit_val("largest-contentful-paint"),
            "fcp_ms": _audit_val("first-contentful-paint"),
            "cls": _audit_val("cumulative-layout-shift"),
            "tbt_ms": _audit_val("total-blocking-time"),
        },
    }


# ─── Custom HTML scrape (zero external deps — pure httpx + regex) ─────
async def _scrape_html(url: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True,
                                       headers={"User-Agent": "AUREM-Audit/1.0 (+aurem.live)"}) as c:
            r = await c.get(url)
            return r.text if r.status_code == 200 else ""
    except Exception as e:
        logger.debug(f"[audit] html fetch failed for {url}: {e}")
        return ""


def _parse_seo(html: str) -> SeoMetadata:
    if not html:
        return SeoMetadata()
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    title = (title_m.group(1).strip() if title_m else "") or None
    desc_m = re.search(
        r'<meta[^>]+name=["\']description["\'][^>]*content=["\']([^"\']+)',
        html, re.I)
    desc = desc_m.group(1).strip() if desc_m else None
    h1s = re.findall(r"<h1[\s>]", html, re.I)
    og_img_m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]*content=["\']([^"\']+)',
        html, re.I)
    canonical_m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)',
        html, re.I)
    has_schema = bool(re.search(r'application/ld\+json', html, re.I))
    imgs = re.findall(r"<img[^>]*>", html, re.I)
    imgs_no_alt = [i for i in imgs if not re.search(r'\salt=', i, re.I)]
    return SeoMetadata(
        title=title,
        title_length=len(title or ""),
        meta_description=desc,
        meta_description_length=len(desc or ""),
        h1_count=len(h1s),
        og_image=og_img_m.group(1) if og_img_m else None,
        canonical_url=canonical_m.group(1) if canonical_m else None,
        has_schema=has_schema,
        img_count=len(imgs),
        img_alt_missing=len(imgs_no_alt),
    )


def _parse_ads(html: str, vitals: CoreWebVitals, seo: SeoMetadata) -> AdsAudit:
    """Heuristic ads-waste detector.

    Detection patterns based on common publisher snippets:
      - Google Ads / Adwords:     `googleadservices.com/pagead/conversion`
      - GTM container:            `googletagmanager.com/gtm.js`
      - GA4:                      `gtag/js?id=G-`
      - Conversion tracking:      `gtag('event', 'conversion'`  or `fbq('track','Purchase')`
      - Remarketing pixel:        `gtag('config', 'AW-`
    Waste signals (each adds an estimated $-figure):
      - Has Google Ads but no conversion tracking → can't optimise: +$200
      - Slow LCP (>2.5s) → ad clicks bounce: +$150
      - Generic title / no CTA above fold: +$100
      - No remarketing pixel → leaving 30% recovery on table: +$80
      - No schema markup → poor ad-quality score: +$50
    Confidence rises with the number of signals found.
    """
    h = html or ""
    has_ads = bool(re.search(r"googleadservices\.com/pagead|/conversion/|aw-conversion",
                              h, re.I))
    has_gtm = "googletagmanager.com/gtm.js" in h
    has_ga4 = bool(re.search(r"gtag/js\?id=G-|gtag\(['\"]config['\"],\s*['\"]G-", h))
    has_conv = bool(re.search(r"gtag\(['\"]event['\"],\s*['\"]conversion['\"]"
                                 r"|fbq\(['\"]track['\"]\s*,\s*['\"](Purchase|Lead)['\"]",
                                 h, re.I))
    has_remarket = bool(re.search(r"gtag\(['\"]config['\"],\s*['\"]AW-", h))
    # Crude CTA-above-fold check: first 8KB of HTML contains a button or call link
    head = h[:8000].lower()
    cta_above = bool(re.search(
        r'<(button|a)[^>]*>\s*(?:get|book|start|try|call|claim|buy|shop|sign[ -]?up)',
        head))

    signals: list[str] = []
    waste = 0
    if has_ads and not has_conv:
        signals.append("Google Ads running but no conversion tracking — you cannot optimise spend.")
        waste += 200
    lcp = (vitals.lcp_ms or 0)
    if lcp > 2500:
        signals.append(f"Slow LCP ({int(lcp)}ms) — ad clicks bounce before content loads.")
        waste += 150
    if (seo.title_length < 20) or (not cta_above):
        signals.append("Generic landing page (no clear CTA above the fold) — low conversion rate.")
        waste += 100
    if has_ads and not has_remarket:
        signals.append("No remarketing pixel — leaving ~30% recovery audience on the table.")
        waste += 80
    if not seo.has_schema:
        signals.append("No Schema.org markup — hurts Google ad quality score and lowers CTR.")
        waste += 50

    confidence = "low"
    if has_ads:
        confidence = "high" if has_conv and has_remarket else "medium"

    return AdsAudit(
        has_google_ads=has_ads,
        has_gtm=has_gtm,
        has_ga4=has_ga4,
        has_conversion_tracking=has_conv,
        has_remarketing=has_remarket,
        cta_above_fold=cta_above,
        waste_signals=signals,
        estimated_monthly_waste_usd=waste,
        confidence=confidence,
    )


# ─── Top issues ranking ───────────────────────────────────────────────
def _rank_top_issues(scores: CategoryScores, vitals: CoreWebVitals,
                      seo: SeoMetadata, ads: AdsAudit,
                      psi_available: bool = True) -> list[str]:
    issues: list[tuple[int, str]] = []
    # Skip Lighthouse-driven issues if PSI didn't run (avoids "Performance 0/100"
    # noise when the API key needs PageSpeed enabled on Google Cloud Console).
    if psi_available:
        if scores.performance < 60:
            issues.append((100 - scores.performance,
                              f"Performance is {scores.performance}/100 — pages feel slow."))
        if (vitals.lcp_ms or 0) > 2500:
            issues.append((90, f"LCP is {int(vitals.lcp_ms or 0)}ms (target <2500ms)."))
        if scores.seo < 80:
            issues.append((80 - scores.seo + 20, f"SEO score is {scores.seo}/100."))
    if seo.title_length < 20 or seo.title_length > 65:
        issues.append((40, "Page title too short or too long for search snippets."))
    if not seo.meta_description:
        issues.append((35, "Missing meta description — losing search-result CTR."))
    if seo.h1_count != 1:
        issues.append((30, f"{seo.h1_count} H1 tags found — should be exactly 1."))
    if seo.img_alt_missing > 0:
        issues.append((25, f"{seo.img_alt_missing} images missing alt text (accessibility + SEO)."))
    if not seo.has_schema:
        issues.append((20, "No Schema.org JSON-LD — invisible to rich results."))
    issues.extend((50 + i * 5, s) for i, s in enumerate(ads.waste_signals[:3]))
    issues.sort(key=lambda x: -x[0])
    return [s for _, s in issues[:6]]


# ─── Orchestrator ────────────────────────────────────────────────────
async def run_audit(
    url: str,
    customer_id: str,
    bin: Optional[str] = None,
    strategy: str = "mobile",
    db=None,
) -> CustomerAudit:
    """End-to-end audit. Persists result to db.customer_audits."""
    audit = CustomerAudit(
        customer_id=customer_id, bin=bin, url=url, strategy=strategy,
    )
    t0 = datetime.now(timezone.utc)

    try:
        # Parallel: PageSpeed + raw HTML scrape
        psi_task = asyncio.create_task(_pagespeed(url, strategy))
        html_task = asyncio.create_task(_scrape_html(url))
        psi_data, html = await asyncio.gather(psi_task, html_task)

        # PSI availability flag (separate from request failure)
        if psi_data.get("_unavailable"):
            audit.psi_status = psi_data["_unavailable"]
            psi_data = {}
        scores_d = (psi_data.get("scores") or {})
        vitals_d = (psi_data.get("core_vitals") or {})
        audit.scores = CategoryScores(**scores_d) if scores_d else CategoryScores()
        audit.core_vitals = CoreWebVitals(**vitals_d) if vitals_d else CoreWebVitals()
        audit.seo = _parse_seo(html)
        audit.ads = _parse_ads(html, audit.core_vitals, audit.seo)
        audit.top_issues = _rank_top_issues(
            audit.scores, audit.core_vitals, audit.seo, audit.ads,
            psi_available=(audit.psi_status == "ok"),
        )
        audit.status = "completed"
    except Exception as e:
        audit.status = "failed"
        audit.error = str(e)[:300]
        logger.exception(f"[audit] run failed for {url}: {e}")

    audit.completed_at = datetime.now(timezone.utc).isoformat()
    audit.duration_ms = int((datetime.now(timezone.utc) - t0).total_seconds() * 1000)

    if db is not None:
        try:
            doc = audit.model_dump()
            doc["_id"] = audit.id
            await db.customer_audits.insert_one(doc)
            await db.customer_audit_metrics.insert_one({
                "_id": f"m_{audit.id}",
                "customer_id": customer_id,
                "duration_ms": audit.duration_ms,
                "status": audit.status,
                "perf_score": audit.scores.performance,
                "seo_score": audit.scores.seo,
                "estimated_waste_usd": audit.ads.estimated_monthly_waste_usd,
                "ts": audit.completed_at,
            })
        except Exception as e:
            logger.warning(f"[audit] persist failed: {e}")

    return audit


async def get_latest_audit(db, customer_id: str) -> Optional[dict]:
    if db is None:
        return None
    return await db.customer_audits.find_one(
        {"customer_id": customer_id},
        {"_id": 0},
        sort=[("started_at", -1)],
    )


async def list_audits(db, customer_id: str, limit: int = 20) -> list[dict]:
    if db is None:
        return []
    cur = db.customer_audits.find(
        {"customer_id": customer_id}, {"_id": 0}
    ).sort("started_at", -1).limit(limit)
    return await cur.to_list(length=limit)


async def ensure_indexes(db) -> None:
    if db is None:
        return
    await db.customer_audits.create_index([("customer_id", 1), ("started_at", -1)])
    await db.customer_audits.create_index("bin")
