"""
Web Search Service for WhatsApp AI Fallback
═══════════════════════════════════════════════════════════════════
Searches the web for reroots.ca related content when RAG confidence is low.
Uses multiple fallback methods for reliability.
═══════════════════════════════════════════════════════════════════
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Search configuration
SEARCH_TIMEOUT = 10  # seconds
MAX_RESULTS = 3
SITE_DOMAIN = "reroots.ca"

# Static fallback knowledge for common queries
STATIC_KNOWLEDGE = {
    "shipping": """
ReRoots Shipping Policy:
- FREE shipping on orders $75+ within Canada
- Standard shipping: 5-7 business days
- Express shipping: 2-3 business days (additional fee)
- All orders are shipped from Canada
- Tracking provided via email once shipped
- International shipping available (contact for rates)
""",
    "return": """
ReRoots Return Policy:
- 30-day return window for unopened products
- Products must be in original packaging
- Contact support@reroots.ca to initiate return
- Refunds processed within 5-7 business days
- Opened products may be exchanged if defective
""",
    "contact": """
ReRoots Contact Information:
- Email: support@reroots.ca
- Website: https://reroots.ca
- Business Hours: Mon-Fri 9am-6pm EST
- Location: Canada
""",
    "free shipping": """
ReRoots offers FREE shipping on orders $75+ within Canada.
Standard delivery takes 5-7 business days.
""",
}


async def search_web_for_reroots(query: str) -> str:
    """
    Search for reroots.ca-related information.
    
    Uses a cascading approach:
    1. Check static knowledge base for common queries
    2. Try web search APIs
    3. Return helpful fallback message
    
    Args:
        query: Customer's question/search query
    
    Returns:
        Formatted string of search results for LLM context
    """
    query_lower = query.lower()
    
    # Step 1: Check static knowledge for common queries
    for keyword, info in STATIC_KNOWLEDGE.items():
        if keyword in query_lower:
            logger.info(f"Web search: Found static knowledge for '{keyword}'")
            return f"--- POLICY INFORMATION ---\n{info.strip()}"
    
    # Step 2: Try Brave Search API if available
    brave_api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if brave_api_key:
        results = await _brave_search(query, brave_api_key)
        if results:
            return _format_results(results)
    
    # Step 3: Try SearXNG public instance (privacy-focused)
    results = await _searxng_search(f"site:{SITE_DOMAIN} {query}")
    if results:
        return _format_results(results)
    
    # Step 4: Fallback - provide helpful guidance
    logger.info(f"Web search: No results found for '{query}', using fallback")
    return _get_fallback_guidance(query)


async def _brave_search(query: str, api_key: str) -> List[Dict[str, Any]]:
    """Search using Brave Search API."""
    try:
        url = "https://api.search.brave.com/res/v1/web/search"
        
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            response = await client.get(
                url,
                params={
                    "q": f"site:{SITE_DOMAIN} {query}",
                    "count": MAX_RESULTS
                },
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": api_key
                }
            )
            
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            
            for item in data.get("web", {}).get("results", [])[:MAX_RESULTS]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("description", "")
                })
            
            return results
            
    except Exception as e:
        logger.warning(f"Brave search error: {e}")
        return []


async def _searxng_search(query: str) -> List[Dict[str, Any]]:
    """Search using public SearXNG instance."""
    try:
        # Use a public SearXNG instance
        instances = [
            "https://searx.be",
            "https://search.bus-hit.me",
        ]
        
        for instance in instances:
            try:
                url = f"{instance}/search"
                
                async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
                    response = await client.get(
                        url,
                        params={
                            "q": query,
                            "format": "json",
                            "engines": "google,bing"
                        },
                        headers={
                            "User-Agent": "Mozilla/5.0 (compatible; RerootsBot/1.0)"
                        }
                    )
                    
                    if response.status_code != 200:
                        continue
                    
                    data = response.json()
                    results = []
                    
                    for item in data.get("results", [])[:MAX_RESULTS]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", "")
                        })
                    
                    if results:
                        return results
                        
            except Exception as e:
                logger.debug(f"SearXNG instance {instance} failed: {e}")
                continue
        
        return []
        
    except Exception as e:
        logger.warning(f"SearXNG search error: {e}")
        return []


def _format_results(results: List[Dict[str, Any]]) -> str:
    """Format search results for LLM context."""
    if not results:
        return ""
    
    parts = ["--- WEB SEARCH RESULTS ---"]
    
    for i, result in enumerate(results, 1):
        title = result.get("title", "")
        url = result.get("url", "")
        snippet = result.get("snippet", "")
        
        entry = f"[{i}] {title}"
        if url:
            entry += f"\n    URL: {url}"
        if snippet:
            entry += f"\n    {snippet}"
        
        parts.append(entry)
    
    parts.append("\nUse this to supplement product knowledge. Prefer database info if conflicting.")
    
    return "\n\n".join(parts)


def _get_fallback_guidance(query: str) -> str:
    """Provide helpful fallback when web search fails."""
    query_lower = query.lower()
    
    # Detect intent and provide appropriate guidance
    if any(w in query_lower for w in ["ship", "deliver", "arrive"]):
        return f"--- GENERAL GUIDANCE ---\nFor shipping questions, customers should check reroots.ca/shipping or email support@reroots.ca for specific delivery times."
    
    if any(w in query_lower for w in ["return", "refund", "exchange"]):
        return f"--- GENERAL GUIDANCE ---\nFor returns or refunds, customers should email support@reroots.ca with their order number."
    
    if any(w in query_lower for w in ["price", "cost", "pay"]):
        return f"--- GENERAL GUIDANCE ---\nFor pricing questions, refer to the product database. All prices are in CAD."
    
    # Generic fallback
    return ""


async def search_for_policies(query: str) -> str:
    """
    Search specifically for shipping, return, and policy information.
    """
    policy_keywords = ["shipping", "return", "refund", "delivery", "canada", "free shipping"]
    
    # Check if query is policy-related
    query_lower = query.lower()
    is_policy_query = any(kw in query_lower for kw in policy_keywords)
    
    if not is_policy_query:
        return ""
    
    return await search_web_for_reroots(query)


# Quick test
if __name__ == "__main__":
    async def test():
        result = await search_web_for_reroots("shipping policy canada")
        print(result)
    
    asyncio.run(test())
