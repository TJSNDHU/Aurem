"""
AUREM — Autonomous Client Website Intelligence Scanner Service.
Scans any client website using Google PageSpeed API + internal checks.
Stores results in scan_history collection. Runs daily via APScheduler.
"""
import asyncio
import logging
import httpx
from datetime import datetime, timezone

logger = logging.getLogger("aurem.client_scanner")

PAGESPEED_API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


class ClientScannerService:
    def __init__(self, db):
        self.db = db

    async def run_full_scan(self, tenant_id: str, website_url: str, triggered_by: str = "manual") -> dict:
        """Run all scan categories in parallel for a client website."""
        logger.info(f"[SCANNER] Starting full scan: tenant={tenant_id} url={website_url}")
        start = datetime.now(timezone.utc)

        result = {
            "tenant_id": tenant_id,
            "url": website_url,
            "scanned_at": start.isoformat(),
            "triggered_by": triggered_by,
            "overall_score": 0,
            "scores": {},
            "issues": [],
            "auto_fixed": [],
            "needs_attention": [],
            "status": "completed",
        }

        try:
            pagespeed, security, uptime = await asyncio.gather(
                self.scan_pagespeed(website_url),
                self.scan_security_headers(website_url),
                self.scan_uptime(website_url),
                return_exceptions=True,
            )

            if isinstance(pagespeed, Exception):
                pagespeed = {"score": 0, "error": str(pagespeed), "issues": []}
            if isinstance(security, Exception):
                security = {"score": 0, "error": str(security), "issues": []}
            if isinstance(uptime, Exception):
                uptime = {"score": 0, "error": str(uptime), "issues": []}

            result["scores"] = {
                "performance": pagespeed.get("performance", 0),
                "accessibility": pagespeed.get("accessibility", 0),
                "seo": pagespeed.get("seo", 0),
                "best_practices": pagespeed.get("best_practices", 0),
                "security": security.get("score", 0),
                "uptime": uptime.get("score", 0),
            }

            result["pagespeed_raw"] = {
                "lcp": pagespeed.get("lcp", "N/A"),
                "fcp": pagespeed.get("fcp", "N/A"),
                "cls": pagespeed.get("cls", "N/A"),
                "tbt": pagespeed.get("tbt", "N/A"),
                "si": pagespeed.get("si", "N/A"),
            }

            all_issues = pagespeed.get("issues", []) + security.get("issues", []) + uptime.get("issues", [])
            result["issues"] = all_issues
            result["issues_count"] = len(all_issues)
            result["critical_count"] = sum(1 for i in all_issues if i.get("severity") == "critical")
            result["fixable_count"] = sum(1 for i in all_issues if i.get("fixable"))

            valid_scores = [v for v in result["scores"].values() if isinstance(v, (int, float)) and v > 0]
            result["overall_score"] = int(sum(valid_scores) / len(valid_scores)) if valid_scores else 0

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            result["scan_duration_seconds"] = round(elapsed, 1)

        except Exception as e:
            logger.error(f"[SCANNER] Full scan failed: {e}")
            result["status"] = "failed"
            result["error"] = str(e)

        await self.db.client_scan_results.insert_one({**result, "_id": f"scan_{tenant_id}_{int(start.timestamp())}"})
        logger.info(f"[SCANNER] Completed: score={result['overall_score']}/100 issues={result.get('issues_count', 0)}")
        return result

    async def scan_pagespeed(self, url: str) -> dict:
        """Call Google PageSpeed Insights API. Falls back to lightweight check if rate limited."""
        import os
        api_key = os.environ.get("GOOGLE_PAGESPEED_API_KEY", "")
        api_url = (
            f"{PAGESPEED_API}?url={url}"
            "&strategy=mobile"
            "&category=performance"
            "&category=accessibility"
            "&category=seo"
            "&category=best-practices"
        )
        if api_key:
            api_url += f"&key={api_key}"

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                r = await client.get(api_url)
                data = r.json()

            if "error" in data:
                error_code = data["error"].get("code", 0)
                if error_code in (429, 403):
                    logger.warning(f"[SCANNER] PageSpeed API rate limited ({error_code}), using lightweight fallback")
                    return await self._lightweight_performance_check(url)
                return {"score": 0, "error": data["error"].get("message", "Unknown"), "issues": []}

            cats = data.get("lighthouseResult", {}).get("categories", {})
            audits = data.get("lighthouseResult", {}).get("audits", {})

            perf = int(cats.get("performance", {}).get("score", 0) * 100)
            access = int(cats.get("accessibility", {}).get("score", 0) * 100)
            seo = int(cats.get("seo", {}).get("score", 0) * 100)
            bp = int(cats.get("best-practices", {}).get("score", 0) * 100)

            issues = []

            lcp_audit = audits.get("largest-contentful-paint", {})
            if lcp_audit.get("score", 1) < 0.9:
                issues.append({
                    "type": "performance", "severity": "high",
                    "title": "Slow LCP (Largest Contentful Paint)",
                    "detail": lcp_audit.get("displayValue", ""),
                    "fixable": False,
                })

            cls_audit = audits.get("cumulative-layout-shift", {})
            if cls_audit.get("score", 1) < 0.9:
                issues.append({
                    "type": "performance", "severity": "medium",
                    "title": "Layout shift detected (CLS)",
                    "detail": cls_audit.get("displayValue", ""),
                    "fixable": False,
                })

            alt_audit = audits.get("image-alt", {})
            if alt_audit.get("score", 1) < 1:
                issues.append({
                    "type": "accessibility", "severity": "medium",
                    "title": "Images missing alt text",
                    "detail": f"{len(alt_audit.get('details', {}).get('items', []))} images",
                    "fixable": True, "auto_fix": "add_alt_tags",
                })

            meta_audit = audits.get("meta-description", {})
            if meta_audit.get("score", 1) < 1:
                issues.append({
                    "type": "seo", "severity": "medium",
                    "title": "Missing meta description",
                    "fixable": True, "auto_fix": "add_meta_description",
                })

            title_audit = audits.get("document-title", {})
            if title_audit.get("score", 1) < 1:
                issues.append({
                    "type": "seo", "severity": "high",
                    "title": "Missing page title",
                    "fixable": True, "auto_fix": "add_page_title",
                })

            https_audit = audits.get("is-on-https", {})
            if https_audit.get("score", 1) < 1:
                issues.append({
                    "type": "security", "severity": "critical",
                    "title": "Not using HTTPS",
                    "fixable": False,
                })

            robots_audit = audits.get("robots-txt", {})
            if robots_audit.get("score", 1) < 1:
                issues.append({
                    "type": "seo", "severity": "low",
                    "title": "Missing or invalid robots.txt",
                    "fixable": True, "auto_fix": "generate_robots_txt",
                })

            viewport_audit = audits.get("viewport", {})
            if viewport_audit.get("score", 1) < 1:
                issues.append({
                    "type": "accessibility", "severity": "high",
                    "title": "No viewport meta tag",
                    "fixable": True, "auto_fix": "add_viewport",
                })

            return {
                "score": perf,
                "performance": perf,
                "accessibility": access,
                "seo": seo,
                "best_practices": bp,
                "lcp": lcp_audit.get("displayValue", "N/A"),
                "fcp": audits.get("first-contentful-paint", {}).get("displayValue", "N/A"),
                "cls": cls_audit.get("displayValue", "N/A"),
                "tbt": audits.get("total-blocking-time", {}).get("displayValue", "N/A"),
                "si": audits.get("speed-index", {}).get("displayValue", "N/A"),
                "issues": issues,
            }
        except Exception as e:
            logger.error(f"[SCANNER] PageSpeed API failed: {e}")
            return {"score": 0, "error": str(e), "issues": []}

    async def scan_security_headers(self, url: str) -> dict:
        """Check security headers (HSTS, CSP, X-Frame-Options, etc.)."""
        score = 100
        issues = []

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.head(url)
                headers = {k.lower(): v for k, v in r.headers.items()}

            checks = [
                ("strict-transport-security", "Missing HSTS header", 15),
                ("content-security-policy", "Missing Content-Security-Policy", 10),
                ("x-frame-options", "Missing X-Frame-Options (clickjacking risk)", 10),
                ("x-content-type-options", "Missing X-Content-Type-Options", 5),
                ("referrer-policy", "Missing Referrer-Policy", 5),
                ("permissions-policy", "Missing Permissions-Policy", 5),
            ]

            for header, title, penalty in checks:
                if header not in headers:
                    score -= penalty
                    issues.append({
                        "type": "security", "severity": "medium",
                        "title": title, "fixable": False,
                    })

            return {"score": max(score, 0), "issues": issues}
        except Exception as e:
            return {"score": 0, "error": str(e), "issues": []}

    async def scan_uptime(self, url: str) -> dict:
        """Basic uptime and response time check."""
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                r = await client.get(url)
                elapsed_ms = int(r.elapsed.total_seconds() * 1000)

            issues = []
            score = 100

            if r.status_code >= 500:
                score = 0
                issues.append({"type": "uptime", "severity": "critical", "title": f"Server error: HTTP {r.status_code}", "fixable": False})
            elif r.status_code >= 400:
                score = 50
                issues.append({"type": "uptime", "severity": "high", "title": f"Client error: HTTP {r.status_code}", "fixable": False})

            if elapsed_ms > 3000:
                score = min(score, 60)
                issues.append({"type": "uptime", "severity": "high", "title": f"Slow response: {elapsed_ms}ms", "fixable": False})
            elif elapsed_ms > 1500:
                score = min(score, 80)
                issues.append({"type": "uptime", "severity": "medium", "title": f"Moderate response: {elapsed_ms}ms", "fixable": False})

            return {"score": score, "response_time_ms": elapsed_ms, "status_code": r.status_code, "issues": issues}
        except Exception as e:
            return {"score": 0, "error": str(e), "issues": [{"type": "uptime", "severity": "critical", "title": "Site unreachable", "fixable": False}]}


    async def _lightweight_performance_check(self, url: str) -> dict:
        """Fallback when PageSpeed API is unavailable. Uses httpx to check basic SEO/accessibility markers."""
        issues = []
        perf_score = 70  # Base score for sites that load
        seo_score = 100
        access_score = 100

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                r = await client.get(url)
                html = r.text.lower()
                elapsed_ms = int(r.elapsed.total_seconds() * 1000)

            # Performance: response time
            if elapsed_ms > 4000:
                perf_score = 40
                issues.append({"type": "performance", "severity": "high", "title": f"Very slow response: {elapsed_ms}ms", "fixable": False})
            elif elapsed_ms > 2000:
                perf_score = 60
                issues.append({"type": "performance", "severity": "medium", "title": f"Slow response: {elapsed_ms}ms", "fixable": False})
            else:
                perf_score = 85

            # SEO checks
            if "<title>" not in html or "<title></title>" in html:
                seo_score -= 20
                issues.append({"type": "seo", "severity": "high", "title": "Missing or empty page title", "fixable": True, "auto_fix": "add_page_title"})
            if 'name="description"' not in html:
                seo_score -= 15
                issues.append({"type": "seo", "severity": "medium", "title": "Missing meta description", "fixable": True, "auto_fix": "add_meta_description"})
            if 'name="viewport"' not in html:
                access_score -= 20
                issues.append({"type": "accessibility", "severity": "high", "title": "Missing viewport meta tag", "fixable": True, "auto_fix": "add_viewport"})
            if '<h1' not in html:
                seo_score -= 10
                issues.append({"type": "seo", "severity": "medium", "title": "Missing H1 heading", "fixable": False})
            if 'alt=' not in html and '<img' in html:
                access_score -= 15
                issues.append({"type": "accessibility", "severity": "medium", "title": "Images missing alt text", "fixable": True, "auto_fix": "add_alt_tags"})

            return {
                "score": perf_score,
                "performance": perf_score,
                "accessibility": access_score,
                "seo": seo_score,
                "best_practices": 75,  # Estimated
                "lcp": f"{elapsed_ms}ms (estimated)",
                "fcp": "N/A",
                "cls": "N/A",
                "tbt": "N/A",
                "si": "N/A",
                "issues": issues,
                "source": "lightweight_fallback",
            }
        except Exception as e:
            logger.error(f"[SCANNER] Lightweight check failed: {e}")
            return {"score": 0, "error": str(e), "issues": []}
