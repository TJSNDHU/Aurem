"""
AUREM Customer System Scanner
Analyzes customer websites/systems and generates comprehensive reports
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import httpx
import asyncio
import re
from bs4 import BeautifulSoup
import time

router = APIRouter()

class ScanRequest(BaseModel):
    website_url: HttpUrl
    include_performance: bool = True
    include_security: bool = True
    include_seo: bool = True
    include_accessibility: bool = True

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

async def scan_performance(url: str) -> Dict[str, Any]:
    """Analyze website performance"""
    issues = []
    metrics = {}
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            response = await client.get(str(url))
            load_time = time.time() - start_time
            
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(str(url))
            headers = response.headers
            
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
    """Analyze SEO optimization"""
    issues = []
    metrics = {}
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check title tag
        title = soup.find('title')
        if not title or not title.string:
            issues.append({
                "severity": "critical",
                "category": "seo",
                "issue": "Missing page title",
                "details": "No <title> tag found",
                "aurem_solution": "AUREM auto-generates SEO-optimized titles"
            })
        elif len(title.string) < 30 or len(title.string) > 60:
            issues.append({
                "severity": "warning",
                "category": "seo",
                "issue": "Suboptimal title length",
                "details": f"Title is {len(title.string)} chars (ideal: 30-60)",
                "aurem_solution": "AUREM optimizes title tags for search engines"
            })
        
        # Check meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc or not meta_desc.get('content'):
            issues.append({
                "severity": "warning",
                "category": "seo",
                "issue": "Missing meta description",
                "details": "No meta description found",
                "aurem_solution": "AUREM generates compelling meta descriptions"
            })
        
        # Check headings
        h1_tags = soup.find_all('h1')
        if len(h1_tags) == 0:
            issues.append({
                "severity": "warning",
                "category": "seo",
                "issue": "No H1 heading",
                "details": "Page has no H1 tag",
                "aurem_solution": "AUREM structures content with proper headings"
            })
        elif len(h1_tags) > 1:
            issues.append({
                "severity": "warning",
                "category": "seo",
                "issue": "Multiple H1 headings",
                "details": f"Found {len(h1_tags)} H1 tags (should have 1)",
                "aurem_solution": "AUREM ensures proper heading hierarchy"
            })
        
        # Check images alt text
        images = soup.find_all('img')
        images_without_alt = [img for img in images if not img.get('alt')]
        if images_without_alt:
            issues.append({
                "severity": "warning",
                "category": "seo",
                "issue": "Images missing alt text",
                "details": f"{len(images_without_alt)} of {len(images)} images lack alt text",
                "aurem_solution": "AUREM adds AI-generated alt text to all images"
            })
        
        metrics['images_total'] = len(images)
        metrics['images_without_alt'] = len(images_without_alt)
        
    except Exception as e:
        issues.append({
            "severity": "warning",
            "category": "seo",
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
    """Analyze accessibility"""
    issues = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Check for lang attribute
        html_tag = soup.find('html')
        if not html_tag or not html_tag.get('lang'):
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "issue": "Missing language declaration",
                "details": "No lang attribute on <html> tag",
                "aurem_solution": "AUREM adds proper language declarations"
            })
        
        # Check form labels
        inputs = soup.find_all(['input', 'textarea', 'select'])
        inputs_without_labels = []
        for inp in inputs:
            inp_id = inp.get('id')
            if inp_id:
                label = soup.find('label', attrs={'for': inp_id})
                if not label and not inp.get('aria-label'):
                    inputs_without_labels.append(inp)
        
        if inputs_without_labels:
            issues.append({
                "severity": "warning",
                "category": "accessibility",
                "issue": "Form inputs without labels",
                "details": f"{len(inputs_without_labels)} inputs lack labels",
                "aurem_solution": "AUREM ensures all inputs have accessible labels"
            })
        
        # Check contrast (basic check for color values)
        # This is simplified - real contrast checking needs actual color parsing
        styles = soup.find_all('style')
        has_contrast_issues = False
        for style in styles:
            if 'color:#' in str(style) or 'background:' in str(style):
                # Simplified check
                has_contrast_issues = True
        
        if has_contrast_issues:
            issues.append({
                "severity": "info",
                "category": "accessibility",
                "issue": "Potential contrast issues",
                "details": "Color contrast should be manually verified",
                "aurem_solution": "AUREM uses WCAG AA compliant color schemes"
            })
        
    except Exception as e:
        issues.append({
            "severity": "warning",
            "category": "accessibility",
            "issue": "Accessibility scan incomplete",
            "details": f"Error: {str(e)}",
            "aurem_solution": "AUREM provides WCAG 2.1 compliant interfaces"
        })
    
    return {
        "score": max(0, 100 - len([i for i in issues if i['severity'] == 'critical']) * 30 - len([i for i in issues if i['severity'] == 'warning']) * 10),
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
            except:
                pass
        
        # Generate scan ID
        scan_id = f"scan_{secrets.token_urlsafe(16)}"
        
        # Fetch website content
        html_content = ""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(str(request.website_url))
                html_content = response.text
        except Exception as e:
            print(f"[Scanner] Failed to fetch content: {e}")
        
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
        
        # Create scan result WITH deep scan data
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
            
            # NEW: Deep scan discoveries
            "deep_scan": deep_scan_results
        }
        
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
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.post("/api/scanner/calculate-pricing")
async def calculate_pricing(scan_id: str = None, issues_count: int = None, critical_count: int = None):
    """
    Calculate suggested pricing based on scan results
    Returns tiered pricing recommendations
    """
    try:
        from server import db
        
        # If scan_id provided, get data from scan
        if scan_id:
            scan = await db.system_scans.find_one({"_id": scan_id}, {"_id": 0})
            if not scan:
                raise HTTPException(status_code=404, detail="Scan not found")
            
            issues_count = scan['issues_found']
            critical_count = scan['critical_issues']
            impact = scan['aurem_impact']
            time_saved = impact.get('estimated_time_saved_monthly', '60 hours')
            cost_savings = impact.get('estimated_cost_savings_monthly', '$1,500')
        else:
            # Use provided counts
            if issues_count is None or critical_count is None:
                raise HTTPException(status_code=400, detail="Provide scan_id or issues_count + critical_count")
            
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
        monthly_cost = monthly_price + (setup_fee / 12)
        roi_months = round(setup_fee / (annual_savings_low / 12), 1)
        
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
        raise HTTPException(status_code=500, detail=str(e))

