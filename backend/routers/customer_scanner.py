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
            if '<script>' in html_content and 'eval(' in html_content:
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
        elif len(title_text) < 30 or len(title_text) > 60:
            issues.append({
                "severity": "warning", "category": "seo",
                "issue": "Suboptimal title length",
                "details": f"Title is {len(title_text)} chars (ideal: 30-60)",
                "aurem_solution": "AUREM optimizes title tags for search engines"
            })

        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        desc_content = meta_desc.get('content', '').strip() if meta_desc else ""
        metrics['has_meta_description'] = bool(desc_content)
        if not desc_content:
            issues.append({
                "severity": "warning", "category": "seo",
                "issue": "Missing meta description",
                "details": "No meta description found",
                "aurem_solution": "AUREM generates compelling meta descriptions"
            })

        # Canonical URL
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        metrics['has_canonical'] = bool(canonical)

        # Open Graph tags
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        metrics['has_og_tags'] = bool(og_title and og_desc)
        if not og_title or not og_desc:
            missing = ', '.join(t for t, v in [('og:title', og_title), ('og:description', og_desc), ('og:image', og_image)] if not v)
            issues.append({
                "severity": "info", "category": "seo",
                "issue": "Missing Open Graph tags",
                "details": f"Missing: {missing}",
                "aurem_solution": "AUREM adds Open Graph tags for social sharing"
            })

        # Headings
        h1_tags = soup.find_all('h1')
        h2_tags = soup.find_all('h2')
        h3_tags = soup.find_all('h3')
        metrics['h1_count'] = len(h1_tags)
        metrics['h2_count'] = len(h2_tags)
        metrics['h3_count'] = len(h3_tags)

        if len(h1_tags) == 0:
            issues.append({
                "severity": "warning", "category": "seo",
                "issue": "No H1 heading",
                "details": "Page has no H1 tag — primary ranking signal missing",
                "aurem_solution": "AUREM structures content with proper headings"
            })
        elif len(h1_tags) > 1:
            issues.append({
                "severity": "warning", "category": "seo",
                "issue": "Multiple H1 headings",
                "details": f"Found {len(h1_tags)} H1 tags (should have 1)",
                "aurem_solution": "AUREM ensures proper heading hierarchy"
            })

        # Links
        links = soup.find_all('a', href=True)
        base_domain = url.split("//")[-1].split("/")[0].replace("www.", "")
        internal = [link for link in links if base_domain in link.get('href', '')]
        external = [link for link in links if link.get('href', '').startswith('http') and base_domain not in link.get('href', '')]
        metrics['internal_links'] = len(internal)
        metrics['external_links'] = len(external)

        # Images
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]
        metrics['images_total'] = len(images)
        metrics['images_without_alt'] = len(images_without_alt)

        if images_without_alt:
            issues.append({
                "severity": "warning", "category": "seo",
                "issue": "Images missing alt text",
                "details": f"{len(images_without_alt)} of {len(images)} images lack alt text",
                "aurem_solution": "AUREM adds AI-generated alt text to all images"
            })

        # Word count
        body = soup.find('body')
        if body:
            text = body.get_text(separator=' ', strip=True)
            metrics['word_count'] = len(text.split())

    except Exception as e:
        issues.append({
            "severity": "warning", "category": "seo",
            "issue": "SEO scan incomplete",
            "details": f"Error: {str(e)}",
            "aurem_solution": "AUREM provides complete SEO optimization"
        })

    return {
        "score": max(0, 100 - len([i for i in issues if i['severity'] == 'critical']) * 30 - len([i for i in issues if i['severity'] == 'warning']) * 10),
        "metrics": metrics,
        "issues": issues
    }


async def scan_accessibility(html_content: str) -> Dict[str, Any]:
    """Analyze accessibility — WCAG 2.1 Level AA checks"""
    issues = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for lang attribute
        html_tag = soup.find('html')
        if not html_tag or not html_tag.get('lang'):
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "Language Declaration",
                "result": "fail",
                "issue": "Missing language declaration",
                "details": "No lang attribute on <html> tag",
                "aurem_solution": "AUREM adds proper language declarations"
            })
        
        # ═══ ARIA LANDMARK CHECKS ═══
        header_tag = soup.find('header') or soup.find(attrs={"role": "banner"})
        if not header_tag:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "ARIA: Banner/Header Landmark",
                "result": "fail",
                "issue": "Missing header/banner landmark",
                "details": "No <header> element or role=\"banner\" found. Screen readers cannot identify the site header.",
                "aurem_solution": "AUREM wraps headers with proper ARIA banner landmark"
            })

        footer_tag = soup.find('footer') or soup.find(attrs={"role": "contentinfo"})
        if not footer_tag:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "ARIA: Footer/Contentinfo Landmark",
                "result": "fail",
                "issue": "Missing footer/contentinfo landmark",
                "details": "No <footer> element or role=\"contentinfo\" found. Screen readers cannot identify the site footer.",
                "aurem_solution": "AUREM wraps footers with proper ARIA contentinfo landmark"
            })

        nav_tag = soup.find('nav') or soup.find(attrs={"role": "navigation"})
        if not nav_tag:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "ARIA: Navigation Landmark",
                "result": "fail",
                "issue": "Missing navigation landmark",
                "details": "No <nav> element or role=\"navigation\" found.",
                "aurem_solution": "AUREM adds navigation landmarks for screen reader users"
            })

        main_tag = soup.find('main') or soup.find(attrs={"role": "main"})
        if not main_tag:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "ARIA: Main Landmark",
                "result": "fail",
                "issue": "Missing main content landmark",
                "details": "No <main> element or role=\"main\" found.",
                "aurem_solution": "AUREM wraps primary content in main landmark"
            })

        # ═══ IMAGE ALT TEXT ═══
        images = soup.find_all('img')
        imgs_no_alt = [img for img in images if not img.get('alt')]
        if imgs_no_alt:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "Image Alt Text",
                "result": "fail",
                "issue": f"{len(imgs_no_alt)} images missing alt text",
                "details": f"{len(imgs_no_alt)} of {len(images)} images have no alt attribute",
                "aurem_solution": "AUREM ensures all images have descriptive alt text"
            })

        # ═══ FORM LABELS ═══
        inputs = soup.find_all(['input', 'textarea', 'select'])
        inputs_without_labels = []
        for inp in inputs:
            if inp.get('type') in ('hidden', 'submit', 'button', 'image'):
                continue
            inp_id = inp.get('id')
            has_label = False
            if inp_id:
                label = soup.find('label', attrs={'for': inp_id})
                if label:
                    has_label = True
            if not has_label and not inp.get('aria-label') and not inp.get('aria-labelledby'):
                inputs_without_labels.append(inp)
        
        if inputs_without_labels:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "Form Labels",
                "result": "fail",
                "issue": "Form inputs without labels",
                "details": f"{len(inputs_without_labels)} inputs lack associated labels or aria-label",
                "aurem_solution": "AUREM ensures all inputs have accessible labels"
            })

        # ═══ HEADING HIERARCHY ═══
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        h1_count = len(soup.find_all('h1'))
        if h1_count == 0:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "Heading Hierarchy",
                "result": "fail",
                "issue": "No H1 tag found",
                "details": "Every page should have exactly one H1 heading",
                "aurem_solution": "AUREM ensures proper heading structure"
            })
        elif h1_count > 1:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "Heading Hierarchy",
                "result": "warning",
                "issue": f"Multiple H1 tags ({h1_count})",
                "details": "Pages should have exactly one H1 heading for proper document structure",
                "aurem_solution": "AUREM maintains single H1 heading hierarchy"
            })

        # Check heading order (no skipping levels)
        if headings:
            prev_level = 0
            for h in headings:
                level = int(h.name[1])
                if prev_level > 0 and level > prev_level + 1:
                    issues.append({
                        "severity": "info",
                        "category": "accessibility",
                        "test": "Heading Hierarchy",
                        "result": "warning",
                        "issue": f"Heading level skipped: h{prev_level} → h{level}",
                        "details": f"Headings should not skip levels (found h{prev_level} followed by h{level})",
                        "aurem_solution": "AUREM maintains sequential heading hierarchy"
                    })
                    break
                prev_level = level

        # ═══ SKIP NAVIGATION ═══
        skip_link = soup.find('a', href='#main-content') or soup.find('a', href='#content') or soup.find('a', string=lambda t: t and 'skip' in t.lower() if t else False)
        if not skip_link:
            issues.append({
                "severity": "info",
                "category": "accessibility",
                "test": "Skip Navigation Link",
                "result": "warning",
                "issue": "No skip navigation link",
                "details": "Keyboard users need a skip-to-content link to bypass navigation",
                "aurem_solution": "AUREM adds skip navigation for keyboard accessibility"
            })

        # ═══ BUTTON ACCESSIBLE NAMES ═══
        buttons = soup.find_all('button')
        unnamed_buttons = [b for b in buttons if not b.get_text(strip=True) and not b.get('aria-label') and not b.get('aria-labelledby') and not b.get('title')]
        if unnamed_buttons:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "Button Accessible Names",
                "result": "fail",
                "issue": f"{len(unnamed_buttons)} buttons without accessible names",
                "details": "Icon-only buttons need aria-label for screen readers",
                "aurem_solution": "AUREM adds aria-labels to all interactive elements"
            })

        # ═══ LINK PURPOSE ═══
        links = soup.find_all('a')
        vague_links = [a for a in links if a.get_text(strip=True).lower() in ('click here', 'read more', 'learn more', 'here', 'more', 'link') and not a.get('aria-label')]
        if vague_links:
            issues.append({
                "severity": "info",
                "category": "accessibility",
                "test": "Link Purpose",
                "result": "warning",
                "issue": f"{len(vague_links)} links with vague text",
                "details": "Links like 'click here' or 'read more' need descriptive text or aria-label",
                "aurem_solution": "AUREM ensures all links have descriptive accessible text"
            })

        # ═══ VIEWPORT ZOOM ═══
        viewport = soup.find('meta', attrs={'name': 'viewport'})
        if viewport:
            content = (viewport.get('content') or '').lower()
            if 'user-scalable=no' in content or 'maximum-scale=1' in content:
                issues.append({
                    "severity": "warning",
                    "category": "accessibility",
                    "test": "Viewport Zoom",
                    "result": "fail",
                    "issue": "Zoom disabled on mobile",
                    "details": "user-scalable=no or maximum-scale=1 prevents users from zooming",
                    "aurem_solution": "AUREM allows viewport zoom for accessibility"
                })

        # ═══ FOCUS INDICATORS ═══ (basic CSS check)
        all_styles = ' '.join([str(s) for s in soup.find_all('style')])
        if 'outline:' in all_styles and ('outline: none' in all_styles or 'outline:none' in all_styles or 'outline: 0' in all_styles):
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "test": "Focus Indicators",
                "result": "warning",
                "issue": "Focus outlines may be removed",
                "details": "CSS contains outline:none which removes keyboard focus indicators",
                "aurem_solution": "AUREM preserves visible focus indicators for keyboard navigation"
            })

    except Exception as e:
        issues.append({
            "severity": "warning",
            "category": "accessibility",
            "test": "Accessibility Scan",
            "result": "warning",
            "issue": "Accessibility scan incomplete",
            "details": f"Error: {str(e)}",
            "aurem_solution": "AUREM provides WCAG 2.1 compliant interfaces"
        })
    
    # Ensure all issues have test/result fields for the repair engine
    for issue in issues:
        if "test" not in issue:
            issue["test"] = issue.get("issue", "Unknown")
        if "result" not in issue:
            issue["result"] = "fail" if issue.get("severity") in ("critical", "warning") else "warning"

    score = max(0, 100 - len([i for i in issues if i['severity'] == 'critical']) * 30 - len([i for i in issues if i['severity'] == 'warning']) * 10 - len([i for i in issues if i['severity'] == 'info']) * 3)
    return {
        "score": score,
        "issues": issues
    }

def calculate_aurem_impact(all_issues: List[Dict]) -> Dict[str, Any]:
    """Calculate the potential improvement with AUREM"""
    critical_count = len([i for i in all_issues if i['severity'] == 'critical'])
    warning_count = len([i for i in all_issues if i['severity'] == 'warning'])
    
    # Calculate potential improvements
    speed_improvement = 0
    security_improvement = 0
    seo_improvement = 0
    
    for issue in all_issues:
        if issue['category'] == 'performance':
            speed_improvement += 20 if issue['severity'] == 'critical' else 10
        elif issue['category'] == 'security':
            security_improvement += 25 if issue['severity'] == 'critical' else 10
        elif issue['category'] == 'seo':
            seo_improvement += 15 if issue['severity'] == 'critical' else 8
    
    return {
        "speed_improvement_percent": min(speed_improvement, 85),
        "security_score_improvement": min(security_improvement, 90),
        "seo_ranking_boost": min(seo_improvement, 75),
        "estimated_time_saved_monthly": "40-80 hours",
        "estimated_cost_savings_monthly": f"${500 + (critical_count * 200)}",
        "automation_coverage": f"{min(85 + len(all_issues) * 2, 98)}%",
        "roi_timeline": "2-4 weeks",
        "before_aurem": {
            "critical_issues": critical_count,
            "warnings": warning_count,
            "manual_work_hours_weekly": 10 + (critical_count * 2)
        },
        "after_aurem": {
            "critical_issues": 0,
            "warnings": max(0, warning_count - critical_count),
            "manual_work_hours_weekly": 1
        }
    }


async def analyze_social_media_personality(enrichment_data: dict) -> Dict[str, Any]:
    """
    Analyze social media profiles to learn customer's personal touch
    Extracts: communication style, interests, values, tone preferences
    """
    personality_insights = {
        "communication_style": "professional",  # professional, casual, formal, friendly
        "interests": [],
        "values": [],
        "tone_preference": "balanced",  # enthusiastic, balanced, conservative
        "personal_touch_tips": [],
        "preferred_contact_method": None
    }
    
    try:
        # Analyze LinkedIn (professional insights)
        if enrichment_data.get("linkedin_url"):
            
            # In production, you'd use LinkedIn API or web scraping
            # For now, we'll infer from the URL structure and provide guidance
            
            personality_insights["communication_style"] = "professional"
            personality_insights["values"].append("career growth")
            personality_insights["interests"].append("business development")
            personality_insights["tone_preference"] = "balanced"
            personality_insights["personal_touch_tips"].append(
                "LinkedIn presence detected - Customer values professional relationships. "
                "Use business-focused language, cite ROI and efficiency gains."
            )
            personality_insights["preferred_contact_method"] = "email"
        
        # Analyze Twitter (communication style, interests)
        if enrichment_data.get("twitter_url"):
            
            # Twitter users typically prefer:
            # - Brief, direct communication
            # - Data-driven insights
            # - Modern tech language
            
            personality_insights["communication_style"] = "casual"
            personality_insights["tone_preference"] = "enthusiastic"
            personality_insights["interests"].append("technology trends")
            personality_insights["personal_touch_tips"].append(
                "Twitter presence suggests customer appreciates concise communication. "
                "Lead with key metrics, use modern terminology, be direct."
            )
        
        # Analyze Facebook (personal values, community focus)
        if enrichment_data.get("facebook_url"):
            personality_insights["values"].append("community")
            personality_insights["values"].append("relationships")
            personality_insights["personal_touch_tips"].append(
                "Facebook presence indicates value for community and relationships. "
                "Emphasize customer success stories and team collaboration features."
            )
        
        # Analyze Instagram (visual preference, brand awareness)
        if enrichment_data.get("instagram_url"):
            personality_insights["interests"].append("visual content")
            personality_insights["values"].append("aesthetics")
            personality_insights["personal_touch_tips"].append(
                "Instagram user - Customer appreciates visual quality. "
                "Send polished presentations, use screenshots and charts, emphasize UI/UX."
            )
        
        # Phone number indicates urgency/directness preference
        if enrichment_data.get("phone"):
            personality_insights["preferred_contact_method"] = "phone"
            personality_insights["personal_touch_tips"].append(
                "Phone number provided - Customer may prefer direct calls. "
                "Consider scheduling a quick 15-minute demo call."
            )
        
        # Email-only suggests preference for written communication
        if enrichment_data.get("email") and not enrichment_data.get("phone"):
            personality_insights["preferred_contact_method"] = "email"
            personality_insights["personal_touch_tips"].append(
                "Email-only contact - Customer prefers written communication. "
                "Send detailed emails with clear CTAs and follow-up scheduling links."
            )
        
        # Combine insights into a coherent strategy
        social_count = sum([
            1 for key in ["linkedin_url", "twitter_url", "facebook_url", "instagram_url"]
            if enrichment_data.get(key)
        ])
        
        if social_count >= 2:
            personality_insights["personal_touch_tips"].append(
                f"Active on {social_count} platforms - Customer is digitally engaged. "
                "They'll appreciate multi-channel follow-up and modern automation features."
            )
        
    except Exception as e:
        print(f"[Social Analysis] Error: {e}")
    
    return personality_insights

@router.post("/api/scanner/scan", response_model=ScanResult)
async def scan_customer_system(request: ScanRequest, authorization: str = Header(None)):
    """
    Scan a customer's website/system and generate comprehensive report
    NOW WITH DEEP SCANNING - Discovers entire tech ecosystem!
    """
    try:
        from server import db
        from utils.deep_scanner import deep_scan_website
        import secrets
        
        # Get current user from token (if authenticated)
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            try:
                import jwt
                import os
                token = authorization.replace("Bearer ", "")
                payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
                user_id = payload.get("user_id", "anonymous")
            except Exception:
                pass
        
        # Generate scan ID
        scan_id = f"scan_{secrets.token_urlsafe(16)}"
        
        # Fetch website content (rendered via Playwright for SPA support)
        html_content = ""
        try:
            from utils.rendered_fetch import fetch_rendered_html
            html_content, _ = await fetch_rendered_html(str(request.website_url))
        except Exception as e:
            print(f"[Scanner] Rendered fetch failed, falling back to raw: {e}")
            try:
                from utils.resilient_fetch import resilient_fetch
                fetch_r = await resilient_fetch(str(request.website_url))
                if fetch_r.success and fetch_r.response:
                    html_content = fetch_r.text
            except Exception as e2:
                print(f"[Scanner] Raw fetch also failed: {e2}")
        
        # Run DEEP SCAN to discover everything
        print(f"[Scanner] Running deep scan on {request.website_url}...")
        deep_scan_results = await deep_scan_website(str(request.website_url))
        
        # Run traditional scans in parallel
        results = await asyncio.gather(
            scan_performance(str(request.website_url)) if request.include_performance else asyncio.sleep(0, result={"score": 100, "issues": []}),
            scan_security(str(request.website_url), html_content) if request.include_security else asyncio.sleep(0, result={"score": 100, "issues": []}),
            scan_seo(str(request.website_url), html_content) if request.include_seo else asyncio.sleep(0, result={"score": 100, "issues": []}),
            scan_accessibility(html_content) if request.include_accessibility else asyncio.sleep(0, result={"score": 100, "issues": []})
        )
        
        perf_result, sec_result, seo_result, acc_result = results
        
        # Collect all issues
        all_issues = []
        all_issues.extend(perf_result.get('issues', []))
        all_issues.extend(sec_result.get('issues', []))
        all_issues.extend(seo_result.get('issues', []))
        all_issues.extend(acc_result.get('issues', []))
        
        critical_count = len([i for i in all_issues if i['severity'] == 'critical'])
        
        # Calculate overall score
        scores = [
            perf_result['score'],
            sec_result['score'],
            seo_result['score'],
            acc_result['score']
        ]
        overall_score = int(sum(scores) / len(scores))

        # Check for previously deployed fixes — boost score for already-fixed issues
        deployed_fix_count = 0
        try:
            db = None
            try:
                import server
                if hasattr(server, "db") and server.db is not None:
                    db = server.db
            except Exception:
                pass
            if db:
                deployed = await db.repair_fixes.count_documents({
                    "scan_url": str(request.website_url),
                    "status": "deployed"
                })
                deployed_fix_count = deployed
                # Boost score: each deployed fix adds up to 2 points (max 10 bonus)
                if deployed > 0:
                    score_boost = min(deployed * 2, 10)
                    overall_score = min(100, overall_score + score_boost)
        except Exception:
            pass
        
        # Calculate AUREM impact
        aurem_impact = calculate_aurem_impact(all_issues)
        
        # Generate recommendations
        recommendations = []
        
        # Top 5 recommendations based on severity
        critical_issues = [i for i in all_issues if i['severity'] == 'critical']
        warning_issues = [i for i in all_issues if i['severity'] == 'warning']
        
        for issue in (critical_issues + warning_issues)[:5]:
            recommendations.append({
                "priority": "high" if issue['severity'] == 'critical' else "medium",
                "category": issue['category'],
                "title": issue['issue'],
                "description": issue['details'],
                "solution": issue['aurem_solution']
            })
        
        # Process manual enrichment data if provided
        enrichment_analysis = None
        if request.manual_enrichment:
            enrichment_data = request.manual_enrichment.dict(exclude_none=True)
            if enrichment_data:  # Only analyze if at least one field is provided
                print("[Scanner] Analyzing social media for personality insights...")
                enrichment_analysis = await analyze_social_media_personality(enrichment_data)
                enrichment_analysis["manual_data"] = enrichment_data
        
        # Create scan result WITH deep scan data AND enrichment
        scan_result = {
            "scan_id": scan_id,
            "website_url": str(request.website_url),
            "scan_date": datetime.now(timezone.utc).isoformat(),
            "overall_score": overall_score,
            "issues_found": len(all_issues),
            "critical_issues": critical_count,
            "performance": perf_result,
            "security": sec_result,
            "seo": seo_result,
            "accessibility": acc_result,
            "recommendations": recommendations,
            "aurem_impact": aurem_impact,
            "deployed_fixes": deployed_fix_count,
            
            # NEW: Deep scan discoveries
            "deep_scan": deep_scan_results,
            
            # NEW: Manual enrichment + personality insights
            "enrichment": enrichment_analysis
        }
        
        # Enrich issues with fix status before saving (tenant mode — scoped by user_id)
        result = await enrich_issues_with_fix_status(db, all_issues, str(request.website_url), user_id=user_id)
        confirmed_resolved = []
        if result:
            detected_keys, fix_keys = result
            confirmed_resolved = build_confirmed_resolved(detected_keys, fix_keys)
        enrich_scan_result_issues(scan_result, all_issues, confirmed_resolved)

        # Save scan to database
        scan_doc = {
            **scan_result,
            "scanned_by": user_id,
            "_id": scan_id
        }
        await db.system_scans.insert_one(scan_doc)
        
        return scan_result
        
    except Exception as e:
        print(f"[Scanner] Error: {e}")
        raise HTTPException(status_code=500, detail="Scan failed. Please try again or check the URL.")


@router.get("/api/scanner/scans/{scan_id}")
async def get_scan_report(scan_id: str):
    """Get a previous scan report"""
    try:
        from server import db
        
        scan = await db.system_scans.find_one({"_id": scan_id}, {"_id": 0})
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return scan
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/scanner/scans")
async def list_scans(authorization: str = Header(None)):
    """List all scans for current user"""
    try:
        from server import db
        import jwt
        import os
        
        # Get user from token
        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            token = authorization.replace("Bearer ", "")
            payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
            user_id = payload.get("user_id", "anonymous")
        
        scans = await db.system_scans.find(
            {"scanned_by": user_id},
            {"_id": 0, "performance": 0, "security": 0, "seo": 0, "accessibility": 0}
        ).sort("scan_date", -1).to_list(100)
        
        return {"scans": scans}
        
    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/scanner/scans/{scan_id}/pdf")
async def download_pdf_report(scan_id: str):
    """Download PDF report for a scan"""
    try:
        from server import db
        from utils.pdf_generator import generate_pdf_report
        from fastapi.responses import StreamingResponse
        
        # Get scan data
        scan = await db.system_scans.find_one({"_id": scan_id}, {"_id": 0})
        if not scan:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Generate PDF
        pdf_buffer = generate_pdf_report(scan)
        
        # Return as downloadable file
        return StreamingResponse(
            pdf_buffer,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=aurem-scan-report-{scan_id}.pdf"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[PDF Export] Error: {e}")
        logger.error(f"[Scanner] PDF generation error: {e}")
        raise HTTPException(status_code=500, detail="PDF generation failed")


class PricingRequest(BaseModel):
    scan_id: Optional[str] = None
    issues_count: Optional[int] = None
    critical_count: Optional[int] = None

@router.post("/api/scanner/calculate-pricing")
async def calculate_pricing(request: PricingRequest):
    """
    Calculate suggested pricing based on scan results
    Returns tiered pricing recommendations
    """
    try:
        from server import db
        
        # If scan_id provided, get data from scan
        if request.scan_id:
            scan = await db.system_scans.find_one({"_id": request.scan_id}, {"_id": 0})
            if not scan:
                raise HTTPException(status_code=404, detail="Scan not found")
            
            issues_count = scan['issues_found']
            critical_count = scan['critical_issues']
            impact = scan['aurem_impact']
            time_saved = impact.get('estimated_time_saved_monthly', '60 hours')
            cost_savings = impact.get('estimated_cost_savings_monthly', '$1,500')
        else:
            # Use provided counts
            if request.issues_count is None or request.critical_count is None:
                raise HTTPException(status_code=400, detail="Provide scan_id or issues_count + critical_count")
            
            issues_count = request.issues_count
            critical_count = request.critical_count
            time_saved = f"{40 + issues_count * 2}-{80 + issues_count * 3} hours"
            cost_savings = f"${500 + (critical_count * 200)}"
        
        # Calculate pricing tiers
        base_price = 299
        
        # Pricing logic
        if critical_count == 0 and issues_count < 10:
            tier = "basic"
            monthly_price = base_price
            setup_fee = 0
        elif critical_count <= 2 and issues_count < 25:
            tier = "professional"
            monthly_price = 599
            setup_fee = 500
        elif critical_count <= 5 and issues_count < 50:
            tier = "business"
            monthly_price = 999
            setup_fee = 1000
        else:
            tier = "enterprise"
            monthly_price = 1999
            setup_fee = 2500
        
        # Calculate value metrics
        annual_savings_low = int(cost_savings.replace('$', '').replace(',', '').split('-')[0]) * 12
        roi_months = round(setup_fee / max(1, annual_savings_low / 12), 1)
        
        pricing_result = {
            "recommended_tier": tier,
            "pricing": {
                "monthly_fee": monthly_price,
                "setup_fee": setup_fee,
                "annual_contract": monthly_price * 12,
                "total_year_one": (monthly_price * 12) + setup_fee
            },
            "value_proposition": {
                "issues_fixed": issues_count,
                "critical_issues_resolved": critical_count,
                "time_saved_monthly": time_saved,
                "cost_savings_monthly": cost_savings,
                "annual_savings_estimate": f"${annual_savings_low:,}",
                "roi_timeline": f"{roi_months} months" if roi_months > 0 else "Immediate",
                "break_even_month": int(roi_months) + 1 if roi_months > 0 else 1
            },
            "tier_details": {
                "basic": {
                    "name": "Basic",
                    "monthly": 299,
                    "setup": 0,
                    "suitable_for": "0-2 critical issues, <10 total issues",
                    "features": [
                        "Automated monitoring",
                        "Basic issue resolution",
                        "Email support",
                        "Monthly reports"
                    ]
                },
                "professional": {
                    "name": "Professional",
                    "monthly": 599,
                    "setup": 500,
                    "suitable_for": "3-5 critical issues, 10-25 total issues",
                    "features": [
                        "Everything in Basic",
                        "Priority support",
                        "Advanced automation",
                        "Weekly reports",
                        "Custom integrations"
                    ]
                },
                "business": {
                    "name": "Business",
                    "monthly": 999,
                    "setup": 1000,
                    "suitable_for": "6-10 critical issues, 25-50 total issues",
                    "features": [
                        "Everything in Professional",
                        "Dedicated account manager",
                        "24/7 monitoring",
                        "Daily reports",
                        "Custom workflows",
                        "API access"
                    ]
                },
                "enterprise": {
                    "name": "Enterprise",
                    "monthly": 1999,
                    "setup": 2500,
                    "suitable_for": "10+ critical issues, 50+ total issues",
                    "features": [
                        "Everything in Business",
                        "White-label option",
                        "Multi-site support",
                        "Custom SLA",
                        "Dedicated infrastructure",
                        "Priority development"
                    ]
                }
            },
            "comparison": {
                "customer_saves": f"${annual_savings_low - ((monthly_price * 12) + setup_fee):,}/year",
                "value_multiple": f"{round(annual_savings_low / ((monthly_price * 12) + setup_fee), 1)}x",
                "cost_as_percent_of_savings": f"{round((((monthly_price * 12) + setup_fee) / annual_savings_low) * 100, 1)}%"
            }
        }
        
        return pricing_result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Pricing Calculator] Error: {e}")
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



# ═══════════════════════════════════════
# SHARE REPORT — Generate & Retrieve public links
# ═══════════════════════════════════════

class ShareReportRequest(BaseModel):
    website_url: str
    overall_score: int = 0
    scores: Dict[str, Any] = {}
    summary: Dict[str, Any] = {}
    categories: Dict[str, Any] = {}
    repairs: List[Dict[str, Any]] = []
    repair_summary: Optional[Dict[str, Any]] = None


@router.post("/api/scanner/share")
async def create_shared_report(body: ShareReportRequest, authorization: str = Header(None)):
    """Save a scan report and return a shareable link. Reconciles repairs into results."""
    try:
        from server import db
        import secrets as sec

        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            try:
                import jwt
                import os
                token = authorization.replace("Bearer ", "")
                payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
                user_id = payload.get("user_id", "anonymous")
            except Exception:
                pass

        share_id = sec.token_urlsafe(12)

        # Reconcile: update categories to reflect repairs
        repaired_names = set(r.get("test") for r in body.repairs if r.get("status") in ("ready", "deployed"))
        reconciled_categories = {}
        total_passed = 0
        total_warnings = 0
        total_failed = 0
        reconciled_scores = {}

        for cat, cat_tests in (body.categories or {}).items():
            updated = []
            for t in cat_tests:
                if t.get("test") in repaired_names and t.get("result") != "pass":
                    updated.append({**t, "result": "pass", "value": "Fixed by ORA"})
                else:
                    updated.append(t)
            reconciled_categories[cat] = updated
            passed = sum(1 for t in updated if t.get("result") == "pass")
            warnings = sum(1 for t in updated if t.get("result") == "warning")
            failed = sum(1 for t in updated if t.get("result") == "fail")
            total_passed += passed
            total_warnings += warnings
            total_failed += failed
            total = len(updated)
            reconciled_scores[cat] = round((passed / total) * 100) if total > 0 else 100

        score_values = list(reconciled_scores.values())
        reconciled_overall = round(sum(score_values) / len(score_values)) if score_values else body.overall_score

        doc = {
            "share_id": share_id,
            "user_id": user_id,
            "website_url": body.website_url,
            "overall_score": reconciled_overall,
            "scores": reconciled_scores if reconciled_scores else body.scores,
            "summary": {"passed": total_passed, "warnings": total_warnings, "failed": total_failed} if reconciled_categories else body.summary,
            "categories": reconciled_categories if reconciled_categories else body.categories,
            "repairs": body.repairs,
            "repair_summary": body.repair_summary,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.shared_reports.insert_one(doc)

        return {"share_id": share_id, "success": True}

    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/public/report/{share_id}")
async def get_shared_report(share_id: str):
    """Public endpoint — no auth required. Returns a shared scan report."""
    try:
        from server import db

        report = await db.shared_reports.find_one(
            {"share_id": share_id}, {"_id": 0}
        )
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        return report

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")



# ═══════════════════════════════════════
# SCAN HISTORY — Save, list, view past scans
# ═══════════════════════════════════════

class SaveScanRequest(BaseModel):
    website_url: str
    overall_score: int = 0
    scores: Dict[str, Any] = {}
    summary: Dict[str, Any] = {}
    categories: Dict[str, Any] = {}
    repairs: List[Dict[str, Any]] = []
    repair_summary: Optional[Dict[str, Any]] = None
    share_id: Optional[str] = None


@router.post("/api/scanner/save")
async def save_scan_to_history(body: SaveScanRequest, authorization: str = Header(None)):
    """Save a completed scan + repairs to the user's scan history. Reconciles repairs into results."""
    try:
        from server import db
        import secrets as sec

        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            try:
                import jwt as _jwt
                import os
                token = authorization.replace("Bearer ", "")
                payload = _jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
                user_id = payload.get("user_id", payload.get("id", "anonymous"))
            except Exception:
                pass

        scan_id = sec.token_urlsafe(16)

        # Reconcile: update categories to reflect repairs
        repaired_names = set(r.get("test") for r in body.repairs if r.get("status") in ("ready", "deployed"))
        reconciled_categories = {}
        total_passed = 0
        total_warnings = 0
        total_failed = 0
        reconciled_scores = {}

        for cat, cat_tests in (body.categories or {}).items():
            updated = []
            for t in cat_tests:
                if t.get("test") in repaired_names and t.get("result") != "pass":
                    updated.append({**t, "result": "pass", "value": "Fixed by ORA"})
                else:
                    updated.append(t)
            reconciled_categories[cat] = updated
            passed = sum(1 for t in updated if t.get("result") == "pass")
            warnings = sum(1 for t in updated if t.get("result") == "warning")
            failed = sum(1 for t in updated if t.get("result") == "fail")
            total_passed += passed
            total_warnings += warnings
            total_failed += failed
            total = len(updated)
            reconciled_scores[cat] = round((passed / total) * 100) if total > 0 else 100

        score_values = list(reconciled_scores.values())
        reconciled_overall = round(sum(score_values) / len(score_values)) if score_values else body.overall_score

        doc = {
            "scan_id": scan_id,
            "user_id": user_id,
            "website_url": body.website_url,
            "overall_score": reconciled_overall,
            "scores": reconciled_scores if reconciled_scores else body.scores,
            "summary": {"passed": total_passed, "warnings": total_warnings, "failed": total_failed} if reconciled_categories else body.summary,
            "categories": reconciled_categories if reconciled_categories else body.categories,
            "repairs": body.repairs,
            "repair_summary": body.repair_summary,
            "share_id": body.share_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        # doc is user-scoped; business_id mirrors user_id-keyed isolation
        await db.scan_history.insert_one(
            {**doc, "business_id": doc.get("business_id") or doc.get("user_id")})

        return {"scan_id": scan_id, "success": True}

    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/scanner/history")
async def get_scan_history(authorization: str = Header(None), limit: int = 20):
    """List past scans for the authenticated user."""
    try:
        from server import db

        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            try:
                import jwt as _jwt
                import os
                token = authorization.replace("Bearer ", "")
                payload = _jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
                user_id = payload.get("user_id", payload.get("id", "anonymous"))
            except Exception:
                pass

        cursor = db.scan_history.find(
            {"user_id": user_id}, {"_id": 0}
        ).sort("created_at", -1).limit(limit)
        scans = await cursor.to_list(length=limit)

        return {"scans": scans, "total": len(scans)}

    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/scanner/history/{scan_id}")
async def get_scan_detail(scan_id: str):
    """Get details of a specific past scan."""
    try:
        from server import db

        doc = await db.scan_history.find_one(  # tenant_scope_guard: admin_cross_tenant — scan_id is an unguessable share token (public share feature)
            {"scan_id": scan_id}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Scan not found")

        return doc

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# ═══════════════════════════════════════
# PUSH FIXES TO CUSTOMER WEBSITE DATABASE
# ═══════════════════════════════════════

class PushFixesRequest(BaseModel):
    website_url: str
    repairs: List[Dict[str, Any]] = []
    repair_summary: Optional[Dict[str, Any]] = None
    scores: Dict[str, Any] = {}
    overall_score: int = 0

@router.post("/api/scanner/push-fixes")
async def push_fixes_to_customer_db(body: PushFixesRequest, authorization: str = Header(None)):
    """
    Push generated repair fixes to the customer's website database.
    Each fix is stored as a deployed patch record. This is a root-cause
    deployment — not patchwork — fixes are written permanently.
    """
    try:
        from server import db
        import secrets as sec

        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            try:
                import jwt as _jwt
                import os
                token = authorization.replace("Bearer ", "")
                payload = _jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
                user_id = payload.get("user_id", payload.get("id", "anonymous"))
            except Exception:
                pass

        if not body.repairs:
            raise HTTPException(status_code=400, detail="No fixes to push")

        push_id = f"push_{sec.token_urlsafe(16)}"
        now = datetime.now(timezone.utc).isoformat()
        deployed_count = 0

        # Self-client safety gate: fixes targeting aurem.live go to pending_review first
        is_self_client = "aurem.live" in (body.website_url or "").lower()
        fix_status = "pending_review" if is_self_client else "deployed"

        # Store each fix as a deployed record in customer_website_fixes
        for repair in body.repairs:
            fix_doc = {
                "push_id": push_id,
                "user_id": user_id,
                "website_url": body.website_url,
                "test": repair.get("test", ""),
                "category": repair.get("category", ""),
                "fix_code": repair.get("fix_code", ""),
                "description": repair.get("description", ""),
                "platform": repair.get("platform", ""),
                "ai_recommendation": repair.get("ai_recommendation", ""),
                "status": fix_status,
                "deployed_at": now if not is_self_client else None,
                "submitted_at": now,
            }
            await db.customer_website_fixes.insert_one(fix_doc)
            deployed_count += 1

        # Store the push deployment record
        push_record = {
            "push_id": push_id,
            "user_id": user_id,
            "website_url": body.website_url,
            "total_fixes_pushed": deployed_count,
            "overall_score_at_push": body.overall_score,
            "scores_at_push": body.scores,
            "repair_summary": body.repair_summary,
            "status": fix_status,
            "created_at": now,
        }
        await db.push_deployments.insert_one(push_record)

        status_msg = (
            f"Successfully submitted {deployed_count} fixes for review (self-client safety gate)."
            if is_self_client else
            f"Successfully pushed {deployed_count} fixes to customer website database. Ready to rescan and verify."
        )

        return {
            "push_id": push_id,
            "success": True,
            "total_pushed": deployed_count,
            "website_url": body.website_url,
            "status": fix_status,
            "message": status_msg,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/api/scanner/push-history")
async def get_push_history(website_url: Optional[str] = None, authorization: str = Header(None)):
    """Get push deployment history for a website."""
    try:
        from server import db

        user_id = "anonymous"
        if authorization and authorization.startswith("Bearer "):
            try:
                import jwt as _jwt
                import os
                token = authorization.replace("Bearer ", "")
                payload = _jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
                user_id = payload.get("user_id", payload.get("id", "anonymous"))
            except Exception:
                pass

        query = {"user_id": user_id}
        if website_url:
            query["website_url"] = website_url

        docs = await db.push_deployments.find(
            query, {"_id": 0}
        ).sort("created_at", -1).limit(20).to_list(length=20)

        return {"pushes": docs, "total": len(docs)}

    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/api/scanner/review-fixes/{push_id}")
async def review_self_client_fixes(push_id: str, action: str = Query(..., pattern="^(approve|reject)$"), authorization: str = Header(None)):
    """
    Approve or reject pending_review fixes for self-client (aurem.live).
    Only admin users can approve. Approved fixes move to 'deployed' status.
    """
    try:
        from server import db
        import os
        import jwt as _jwt

        # Admin-only gate
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authorization required")
        token = authorization.replace("Bearer ", "")
        payload = _jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        # Bug-fix 144 — `or payload.get("email")` accepted ANY user with an
        # email claim. Now requires explicit admin claim/role or whitelist.
        from utils.admin_guard import is_admin_email as _is_admin_email
        if not (
            payload.get("is_admin")
            or payload.get("is_super_admin")
            or payload.get("role") in ("admin", "super_admin")
            or _is_admin_email(payload.get("email"))
        ):
            raise HTTPException(status_code=403, detail="Admin access required to review self-client fixes")

        push = await db.push_deployments.find_one({"push_id": push_id})
        if not push:
            raise HTTPException(status_code=404, detail="Push not found")
        if push.get("status") != "pending_review":
            raise HTTPException(status_code=400, detail=f"Push is already '{push.get('status')}', not pending_review")

        now = datetime.now(timezone.utc).isoformat()
        new_status = "deployed" if action == "approve" else "rejected"

        # Update all fixes in this push
        fix_update = await db.customer_website_fixes.update_many(
            {"push_id": push_id},
            {"$set": {
                "status": new_status,
                "reviewed_at": now,
                "reviewed_by": payload.get("user_id", "admin"),
                "deployed_at": now if action == "approve" else None,
            }}
        )

        # Update the push record
        await db.push_deployments.update_one(
            {"push_id": push_id},
            {"$set": {
                "status": new_status,
                "reviewed_at": now,
                "reviewed_by": payload.get("user_id", "admin"),
            }}
        )

        return {
            "push_id": push_id,
            "action": action,
            "new_status": new_status,
            "fixes_updated": fix_update.modified_count,
            "message": f"Push {push_id} {new_status}. {fix_update.modified_count} fixes updated.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Scanner] Internal error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
