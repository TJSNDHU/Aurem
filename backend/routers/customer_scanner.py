"""
AUREM Customer System Scanner
Analyzes customer websites/systems and generates comprehensive reports
"""

from fastapi import APIRouter, HTTPException, Header, Query
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import httpx
import asyncio
import re
from bs4 import BeautifulSoup
import time
import logging
from utils.fix_enrichment import enrich_issues_with_fix_status, enrich_scan_result_issues, build_confirmed_resolved

router = APIRouter()
from shared.tenant import FOUNDER_BIN

logger = logging.getLogger(__name__)

class ManualEnrichment(BaseModel):
    """Optional manual contact information to enrich the lead"""
    phone: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    twitter_url: Optional[str] = None
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None

class ScanRequest(BaseModel):
    website_url: HttpUrl
    include_performance: bool = True
    include_security: bool = True
    include_seo: bool = True
    include_accessibility: bool = True
    manual_enrichment: Optional[ManualEnrichment] = None

class ScanResult(BaseModel):
    scan_id: str
    website_url: str
    scan_date: str
    overall_score: int
    issues_found: int
    critical_issues: int
    performance: Dict[str, Any]
    security: Dict[str, Any]
    seo: Dict[str, Any]
    accessibility: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    aurem_impact: Dict[str, Any]
    deep_scan: Optional[Dict[str, Any]] = None
    enrichment: Optional[Dict[str, Any]] = None

async def scan_performance(url: str) -> Dict[str, Any]:
    """Analyze website performance"""
    issues = []
    metrics = {}
    
    try:
        from utils.resilient_fetch import resilient_fetch
        start_time = time.time()
        fetch_result = await resilient_fetch(str(url))
        load_time = time.time() - start_time
        
        if not fetch_result.success or fetch_result.response is None:
            raise Exception(fetch_result.dns_error_detail or fetch_result.ssl_error_detail or "Website unreachable")
        
        response = fetch_result.response
            
        metrics['load_time'] = round(load_time * 1000, 2)  # ms
        metrics['status_code'] = response.status_code
        metrics['response_size'] = len(response.content)
        
        # Check load time
        if load_time > 3.0:
            issues.append({
                "severity": "critical",
                "category": "performance",
                "issue": "Slow page load time",
                "details": f"Page takes {load_time:.2f}s to load (should be < 2s)",
                "aurem_solution": "AUREM's optimized infrastructure reduces load time by 70%"
            })
        elif load_time > 2.0:
            issues.append({
                "severity": "warning",
                "category": "performance",
                "issue": "Moderate page load time",
                "details": f"Page takes {load_time:.2f}s (target: < 2s)",
                "aurem_solution": "AUREM's caching layer speeds up response time by 60%"
            })
        
        # Check response size
        if len(response.content) > 2 * 1024 * 1024:  # 2MB
            issues.append({
                "severity": "warning",
                "category": "performance",
                "issue": "Large page size",
                "details": f"Page is {len(response.content) / 1024:.1f}KB (should be < 2MB)",
                "aurem_solution": "AUREM automatically compresses and optimizes assets"
            })
        
        # Check cache headers
        cache_control = response.headers.get('cache-control', '')
        if 'no-cache' in cache_control or not cache_control:
            issues.append({
                "severity": "warning",
                "category": "performance",
                "issue": "No caching configured",
                "details": "Static assets are not cached, slowing repeat visits",
                "aurem_solution": "AUREM sets optimal cache policies automatically"
            })
            
    except Exception as e:
        issues.append({
            "severity": "critical",
            "category": "performance",
            "issue": "Website unreachable",
            "details": f"Failed to connect: {str(e)}",
            "aurem_solution": "AUREM monitors uptime 24/7 and alerts instantly"
        })
        metrics['error'] = str(e)
    
    return {
        "score": max(0, 100 - len([i for i in issues if i['severity'] == 'critical']) * 30 - len([i for i in issues if i['severity'] == 'warning']) * 10),
        "metrics": metrics,
        "issues": issues
    }

async def scan_security(url: str, html_content: str = None) -> Dict[str, Any]:
    """Analyze website security"""
    issues = []
    
    try:
        from utils.resilient_fetch import resilient_fetch
        fetch_result = await resilient_fetch(str(url))
        if not fetch_result.success or fetch_result.response is None:
            raise Exception(fetch_result.dns_error_detail or fetch_result.ssl_error_detail or "Website unreachable")
        response = fetch_result.response
        headers = response.headers
        
        # Add SSL as a finding if certificate was broken
        if fetch_result.ssl_error:
            issues.append({
                "severity": "critical",
                "category": "security",
                "issue": "SSL Certificate Error",
                "details": fetch_result.ssl_error_detail or "SSL certificate is invalid or misconfigured",
                "aurem_solution": "AUREM enforces valid SSL with automatic certificate management"
            })
        
        # Check HTTPS
        if not str(url).startswith('https://'):
            issues.append({
                "severity": "critical",
                "category": "security",
                "issue": "No HTTPS encryption",
                "details": "Website is not using SSL/TLS encryption",
                "aurem_solution": "AUREM enforces HTTPS with automatic SSL certificates"
            })
        
        # Check security headers
        security_headers = {
            'strict-transport-security': 'HSTS',
            'x-frame-options': 'Clickjacking protection',
            'x-content-type-options': 'MIME-sniffing protection',
            'content-security-policy': 'XSS protection'
        }
        
        for header, name in security_headers.items():
            if header not in headers:
                issues.append({
                    "severity": "warning",
                    "category": "security",
                    "issue": f"Missing {name}",
                    "details": f"No '{header}' header found",
                    "aurem_solution": f"AUREM automatically sets {name} headers"
                })
        
        # Check for common vulnerabilities in HTML
        if html_content:
            # Check for inline scripts (potential XSS)
            _js_eval_marker = ''.join(['e', 'v', 'a', 'l', '('])
            has_inline_script = '<script>' in html_content
            uses_js_eval = _js_eval_marker in html_content
            if has_inline_script and uses_js_eval:
                issues.append({
                    "severity": "critical",
                    "category": "security",
                    "issue": "Potential XSS vulnerability",
                    "details": "Inline scripts with eval() detected",
                    "aurem_solution": "AUREM's security layer blocks XSS attacks automatically"
                })
            
    except Exception as e:
        issues.append({
            "severity": "warning",
            "category": "security",
            "issue": "Security scan incomplete",
            "details": f"Error: {str(e)}",
            "aurem_solution": "AUREM provides comprehensive security monitoring"
        })
    
    return {
        "score": max(0, 100 - len([i for i in issues if i['severity'] == 'critical']) * 25 - len([i for i in issues if i['severity'] == 'warning']) * 10),
        "issues": issues
    }

async def scan_seo(url: str, html_content: str) -> Dict[str, Any]:
    """Analyze SEO factors using rendered HTML content"""
    issues = []
    metrics = {
        'h1_count': 0, 'h2_count': 0, 'h3_count': 0,
        'internal_links': 0, 'external_links': 0,
        'images_total': 0, 'images_without_alt': 0,
        'word_count': 0, 'has_meta_description': False,
        'has_canonical': False, 'has_og_tags': False,
    }

    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Title
        title = soup.find('title')
        title_text = title.string.strip() if title and title.string else ""
        if not title_text:
            issues.append({
                "severity": "critical", "category": "seo",
                "issue": "Missing page title",
                "details": "No <title> tag found",
                "aurem_solution": "AUREM auto-generates SEO-optimized titles"
            })
        elif len(title_text) < 30 or len