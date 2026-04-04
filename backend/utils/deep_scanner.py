"""
AUREM Deep Scanner - Comprehensive System Discovery
Scans everything about a customer's tech stack from just a website URL
"""

import httpx
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import re
from typing import Dict, List, Any

async def deep_scan_website(url: str) -> Dict[str, Any]:
    """
    Comprehensive scan of customer's entire tech ecosystem
    Returns: Complete profile of their business technology
    """
    
    results = {
        "website_analysis": {},
        "tech_stack": {},
        "third_party_services": [],
        "pages_discovered": [],
        "api_endpoints": [],
        "social_media": {},
        "mobile_apps": {},
        "domain_info": {},
        "security_headers": {},
        "performance_metrics": {},
        "business_intelligence": {}
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # 1. Fetch main page
            response = await client.get(str(url))
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Run all scans in parallel
            await asyncio.gather(
                detect_tech_stack(soup, response.headers, results),
                discover_pages(url, soup, client, results),
                find_api_endpoints(soup, response.text, results),
                detect_third_party_services(soup, html_content, results),
                extract_social_media(soup, results),
                detect_mobile_apps(soup, html_content, results),
                analyze_domain(url, results),
                check_security_headers(response.headers, results),
                extract_business_info(soup, html_content, results),
                detect_cms_and_frameworks(soup, response.headers, html_content, results)
            )
            
    except Exception as e:
        print(f"[Deep Scanner] Error: {e}")
        results["error"] = str(e)
    
    return results


async def detect_tech_stack(soup, headers, results):
    """Detect all technologies used"""
    tech_stack = {
        "frontend_frameworks": [],
        "javascript_libraries": [],
        "css_frameworks": [],
        "analytics": [],
        "hosting": None,
        "cdn": None,
        "web_server": None
    }
    
    # Check headers
    server = headers.get('server', '').lower()
    if server:
        tech_stack["web_server"] = server
        if 'nginx' in server:
            tech_stack["hosting"] = "Nginx"
        elif 'apache' in server:
            tech_stack["hosting"] = "Apache"
        elif 'cloudflare' in server:
            tech_stack["cdn"] = "Cloudflare"
    
    # Check for frameworks in scripts
    scripts = soup.find_all('script', src=True)
    for script in scripts:
        src = script.get('src', '').lower()
        
        # Frontend frameworks
        if 'react' in src:
            tech_stack["frontend_frameworks"].append("React")
        if 'vue' in src:
            tech_stack["frontend_frameworks"].append("Vue.js")
        if 'angular' in src:
            tech_stack["frontend_frameworks"].append("Angular")
        if 'next' in src:
            tech_stack["frontend_frameworks"].append("Next.js")
        
        # JavaScript libraries
        if 'jquery' in src:
            tech_stack["javascript_libraries"].append("jQuery")
        if 'lodash' in src:
            tech_stack["javascript_libraries"].append("Lodash")
        
        # Analytics
        if 'google-analytics' in src or 'gtag' in src or 'ga.js' in src:
            tech_stack["analytics"].append("Google Analytics")
        if 'mixpanel' in src:
            tech_stack["analytics"].append("Mixpanel")
        if 'segment' in src:
            tech_stack["analytics"].append("Segment")
        if 'hotjar' in src:
            tech_stack["analytics"].append("Hotjar")
        
        # CDN detection
        if 'cloudflare' in src:
            tech_stack["cdn"] = "Cloudflare"
        elif 'fastly' in src:
            tech_stack["cdn"] = "Fastly"
        elif 'akamai' in src:
            tech_stack["cdn"] = "Akamai"
    
    # Check for CSS frameworks
    links = soup.find_all('link', rel='stylesheet')
    for link in links:
        href = link.get('href', '').lower()
        if 'bootstrap' in href:
            tech_stack["css_frameworks"].append("Bootstrap")
        if 'tailwind' in href:
            tech_stack["css_frameworks"].append("Tailwind CSS")
        if 'material' in href or 'mui' in href:
            tech_stack["css_frameworks"].append("Material UI")
    
    results["tech_stack"] = tech_stack


async def discover_pages(base_url, soup, client, results):
    """Discover all pages/routes on the website"""
    pages = set()
    
    # Find all internal links
    for link in soup.find_all('a', href=True):
        href = link['href']
        full_url = urljoin(str(base_url), href)
        
        # Only internal links
        if urlparse(full_url).netloc == urlparse(str(base_url)).netloc:
            pages.add(full_url)
    
    # Check for sitemap
    try:
        sitemap_url = urljoin(str(base_url), '/sitemap.xml')
        response = await client.get(sitemap_url)
        if response.status_code == 200:
            # Parse sitemap URLs
            sitemap_soup = BeautifulSoup(response.text, 'xml')
            for loc in sitemap_soup.find_all('loc'):
                pages.add(loc.text)
            results["sitemap_found"] = True
    except:
        results["sitemap_found"] = False
    
    results["pages_discovered"] = list(pages)[:50]  # Limit to 50
    results["total_pages_count"] = len(pages)


async def find_api_endpoints(soup, html_content, results):
    """Find exposed API endpoints"""
    api_endpoints = set()
    
    # Search for API URLs in JavaScript
    api_patterns = [
        r'["\']https?://[^"\']*api[^"\']*["\']',
        r'["\']\/api\/[^"\']*["\']',
        r'fetch\(["\']([^"\']+)["\']',
        r'axios\.[get|post|put|delete]+\(["\']([^"\']+)["\']'
    ]
    
    for pattern in api_patterns:
        matches = re.findall(pattern, html_content, re.IGNORECASE)
        for match in matches:
            cleaned = match.strip('"\'')
            if cleaned:
                api_endpoints.add(cleaned)
    
    results["api_endpoints"] = list(api_endpoints)[:20]


async def detect_third_party_services(soup, html_content, results):
    """Detect all third-party services and integrations"""
    services = []
    
    # Payment processors
    if 'stripe' in html_content.lower():
        services.append({"name": "Stripe", "category": "Payment Processing"})
    if 'paypal' in html_content.lower():
        services.append({"name": "PayPal", "category": "Payment Processing"})
    if 'square' in html_content.lower():
        services.append({"name": "Square", "category": "Payment Processing"})
    
    # Email services
    if 'mailchimp' in html_content.lower():
        services.append({"name": "Mailchimp", "category": "Email Marketing"})
    if 'sendgrid' in html_content.lower():
        services.append({"name": "SendGrid", "category": "Email Delivery"})
    if 'mailgun' in html_content.lower():
        services.append({"name": "Mailgun", "category": "Email Delivery"})
    
    # CRM
    if 'salesforce' in html_content.lower():
        services.append({"name": "Salesforce", "category": "CRM"})
    if 'hubspot' in html_content.lower():
        services.append({"name": "HubSpot", "category": "CRM & Marketing"})
    
    # Chat widgets
    if 'intercom' in html_content.lower():
        services.append({"name": "Intercom", "category": "Customer Support"})
    if 'zendesk' in html_content.lower():
        services.append({"name": "Zendesk", "category": "Customer Support"})
    if 'drift' in html_content.lower():
        services.append({"name": "Drift", "category": "Conversational Marketing"})
    if 'tawk.to' in html_content.lower():
        services.append({"name": "Tawk.to", "category": "Live Chat"})
    
    # Social media pixels
    if 'facebook.com/tr' in html_content or 'fbq(' in html_content:
        services.append({"name": "Facebook Pixel", "category": "Advertising"})
    if 'linkedin.com/px' in html_content:
        services.append({"name": "LinkedIn Insight Tag", "category": "Advertising"})
    if 'twitter.com/i/adsct' in html_content:
        services.append({"name": "Twitter Pixel", "category": "Advertising"})
    
    # Maps
    if 'maps.googleapis.com' in html_content:
        services.append({"name": "Google Maps", "category": "Maps"})
    if 'mapbox' in html_content.lower():
        services.append({"name": "Mapbox", "category": "Maps"})
    
    results["third_party_services"] = services


async def extract_social_media(soup, results):
    """Extract all social media profiles"""
    social = {
        "facebook": None,
        "twitter": None,
        "linkedin": None,
        "instagram": None,
        "youtube": None,
        "github": None
    }
    
    # Find social links
    for link in soup.find_all('a', href=True):
        href = link['href'].lower()
        
        if 'facebook.com' in href:
            social["facebook"] = link['href']
        elif 'twitter.com' in href or 'x.com' in href:
            social["twitter"] = link['href']
        elif 'linkedin.com' in href:
            social["linkedin"] = link['href']
        elif 'instagram.com' in href:
            social["instagram"] = link['href']
        elif 'youtube.com' in href:
            social["youtube"] = link['href']
        elif 'github.com' in href:
            social["github"] = link['href']
    
    results["social_media"] = {k: v for k, v in social.items() if v}


async def detect_mobile_apps(soup, html_content, results):
    """Detect mobile apps (iOS/Android)"""
    mobile = {
        "ios_app": None,
        "android_app": None,
        "app_links": []
    }
    
    # Check for app store links
    for link in soup.find_all('a', href=True):
        href = link['href'].lower()
        
        if 'apps.apple.com' in href or 'itunes.apple.com' in href:
            mobile["ios_app"] = link['href']
            mobile["app_links"].append({"platform": "iOS", "url": link['href']})
        elif 'play.google.com' in href:
            mobile["android_app"] = link['href']
            mobile["app_links"].append({"platform": "Android", "url": link['href']})
    
    # Check meta tags
    for meta in soup.find_all('meta'):
        if meta.get('name') == 'apple-itunes-app':
            mobile["ios_app_meta"] = meta.get('content')
        elif meta.get('name') == 'google-play-app':
            mobile["android_app_meta"] = meta.get('content')
    
    results["mobile_apps"] = mobile


async def analyze_domain(url, results):
    """Analyze domain and DNS information"""
    parsed = urlparse(str(url))
    
    domain_info = {
        "domain": parsed.netloc,
        "protocol": parsed.scheme,
        "is_https": parsed.scheme == 'https',
        "subdomain": None
    }
    
    # Check for subdomain
    parts = parsed.netloc.split('.')
    if len(parts) > 2:
        domain_info["subdomain"] = parts[0]
    
    results["domain_info"] = domain_info


async def check_security_headers(headers, results):
    """Analyze security headers"""
    security = {
        "https": False,
        "hsts": headers.get('strict-transport-security') is not None,
        "csp": headers.get('content-security-policy') is not None,
        "x_frame_options": headers.get('x-frame-options'),
        "x_content_type_options": headers.get('x-content-type-options'),
        "referrer_policy": headers.get('referrer-policy'),
        "permissions_policy": headers.get('permissions-policy')
    }
    
    results["security_headers"] = security


async def extract_business_info(soup, html_content, results):
    """Extract business information"""
    business = {
        "company_name": None,
        "description": None,
        "email": None,
        "phone": None,
        "address": None,
        "industry": None
    }
    
    # Try to get from meta tags
    title = soup.find('title')
    if title:
        business["company_name"] = title.text.strip()
    
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    if meta_desc:
        business["description"] = meta_desc.get('content', '')
    
    # Look for emails
    emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', html_content)
    if emails:
        # Filter out common false positives
        valid_emails = [e for e in emails if not any(x in e.lower() for x in ['example.com', 'test.com', 'domain.com'])]
        if valid_emails:
            business["email"] = valid_emails[0]
    
    # Look for phone numbers
    phones = re.findall(r'(\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})', html_content)
    if phones:
        business["phone"] = phones[0]
    
    # Try to detect industry from content
    industries = {
        'ecommerce': ['shop', 'cart', 'buy', 'product', 'store'],
        'saas': ['software', 'platform', 'dashboard', 'api', 'integration'],
        'agency': ['agency', 'marketing', 'design', 'consulting'],
        'education': ['course', 'learn', 'training', 'education', 'academy'],
        'healthcare': ['health', 'medical', 'doctor', 'clinic', 'patient'],
        'finance': ['banking', 'investment', 'financial', 'trading']
    }
    
    content_lower = html_content.lower()
    for industry, keywords in industries.items():
        if sum(1 for kw in keywords if kw in content_lower) >= 2:
            business["industry"] = industry
            break
    
    results["business_intelligence"] = business


async def detect_cms_and_frameworks(soup, headers, html_content, results):
    """Detect CMS and backend frameworks"""
    cms_detected = []
    
    # WordPress
    if 'wp-content' in html_content or 'wp-includes' in html_content:
        cms_detected.append("WordPress")
    
    # Shopify
    if 'shopify' in html_content.lower() or 'cdn.shopify.com' in html_content:
        cms_detected.append("Shopify")
    
    # Wix
    if 'wix.com' in html_content.lower():
        cms_detected.append("Wix")
    
    # Squarespace
    if 'squarespace' in html_content.lower():
        cms_detected.append("Squarespace")
    
    # Webflow
    if 'webflow' in html_content.lower():
        cms_detected.append("Webflow")
    
    # Drupal
    if 'drupal' in html_content.lower():
        cms_detected.append("Drupal")
    
    # Joomla
    if 'joomla' in html_content.lower():
        cms_detected.append("Joomla")
    
    if cms_detected:
        results["tech_stack"]["cms"] = cms_detected[0]
        results["tech_stack"]["all_cms_detected"] = cms_detected
