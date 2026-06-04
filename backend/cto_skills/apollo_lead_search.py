"""Apollo lead search skill."""
from typing import Any

from .registry import skill


@skill(
    name="apollo_lead_search",
    description=(
        "Search Apollo.io for SMB organizations matching an industry "
        "keyword and city. Returns up to `count` real businesses with "
        "verified phone/website."
    ),
    requires_keys=["APOLLO_API_KEY"],
)
async def apollo_lead_search(industry: str, city: str,
                               country: str = "Canada",
                               count: int = 10) -> dict[str, Any]:
    from services.apollo_discovery import discover_organizations
    orgs = await discover_organizations(
        industry_keyword=industry, city=city,
        country=country, per_page=max(1, min(count, 50)),
    )
    return {"industry": industry, "city": city, "country": country,
             "count": len(orgs), "leads": orgs}
