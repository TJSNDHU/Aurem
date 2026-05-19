"""
Contact-Quality Gate
────────────────────
Single source of truth for "is this email/domain a real business contact,
or aggregator/social/SaaS junk?". Used by:
  • apollo_enrichment.py — blocks junk role-email fallback at ingestion
  • auto_blast_engine — final eligibility check (defense in depth)
  • One-shot scrub endpoint that clears junk emails from existing leads

Iter 324b — pulled from the noise list discovered when the campaign
funnel reported `not_noise_flagged=0` despite 421 queued leads with
"emails". Every email was `info@<aggregator>` because hunt_live captures
the first Google-SERP result as `website_url`, and the role-email
fallback built `info@facebook.com` etc.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

# Aggregator / social / SaaS / SERP-noise hosts. Anything here means the
# "domain" isn't actually the business — it's a platform the business
# happens to be listed on.
AGGREGATOR_DOMAINS: frozenset[str] = frozenset({
    # Social
    "facebook.com", "fb.com", "instagram.com", "linkedin.com",
    "twitter.com", "x.com", "tiktok.com", "youtube.com", "youtu.be",
    "pinterest.com", "snapchat.com", "threads.net", "reddit.com",
    # Search / encyclopedia / news
    "google.com", "google.ca", "google.co.uk",
    "bing.com", "duckduckgo.com", "yahoo.com",
    "wikipedia.org", "en.wikipedia.org", "wikimedia.org",
    # Directories / listings
    "yelp.com", "yellowpages.com", "yellowpages.ca", "yp.com",
    "tripadvisor.com", "tripadvisor.ca", "tripadvisor.co.uk",
    "manta.com", "bbb.org", "dandb.com", "dnb.com",
    "chamberofcommerce.com", "canpages.ca", "canadapages.com", "411.ca",
    "houzz.com", "thumbtack.com", "homestars.com",
    "realtor.ca", "realtor.com", "zillow.com", "redfin.com",
    "rew.ca", "zolo.ca", "remax.ca", "remax.com",
    # iter 324c — directory aggregators caught leaking into production sends
    "cylex.ca", "cylex-canada.ca", "cylex.us", "cylex.co.uk", "cylex.de",
    "near.co.uk", "near.com", "near.us",
    "findopen.com", "findopen.ca", "findopen.co.uk",
    "bleen.com", "bleen.ca",
    "hamilton-ohio.com",  # city-name listicle aggregator
    "superlawyers.com", "profiles.superlawyers.com",
    "desiforce.com",  # local SA-Indian SMB directory
    "angi.com", "angieslist.com", "trustpilot.com", "glassdoor.com",
    "crunchbase.com", "indeed.com", "ziprecruiter.com",
    "g.page", "googleusercontent.com",
    # Booking / SaaS aggregators
    "fresha.com", "booksy.com", "vagaro.com", "mindbody.com",
    "schedulicity.com", "squareup.com", "square.site",
    "opentable.com", "resy.com", "yelpreservations.com",
    # E-commerce / delivery aggregators
    "ubereats.com", "doordash.com", "grubhub.com", "skipthedishes.com",
    "amazon.com", "amazon.ca", "ebay.com", "etsy.com",
    "shopify.com", "wix.com", "squarespace.com", "weebly.com",
    "godaddy.com", "wordpress.com", "blogspot.com",
    # Brand chains (false-positive lead-source matches)
    "autozone.com", "walmart.com", "costco.com", "target.com",
    "homedepot.com", "lowes.com", "starbucks.com", "mcdonalds.com",
    # Forums / Q&A
    "quora.com", "stackoverflow.com", "stackexchange.com",
    # Misc SaaS
    "calendly.com", "linktr.ee", "linktree.com", "bitly.com",
    "github.com", "gitlab.com",
})

# Sometimes the "domain" is a sub-page of an aggregator (e.g. "yelp.com/biz/...").
# We still match on the registered root, so substring won't false-match short
# legit names like "fb-marketing.ca".

# Role-email local-parts that aren't actually owned by the business when
# stuck on an aggregator domain. (`info@`, `contact@`, `hello@`, etc.)
_ROLE_LOCALPARTS: frozenset[str] = frozenset({
    "info", "contact", "hello", "sales", "admin", "office",
    "support", "help", "team", "noreply", "no-reply",
})


def _extract_domain(value: str) -> str:
    """Pull the registered-host portion from a URL or email. Lowercased.
    Empty string if we can't parse anything sensible."""
    if not value or not isinstance(value, str):
        return ""
    v = value.strip().lower()
    if "@" in v:
        # email
        v = v.split("@", 1)[1]
    # Strip protocol + path + query
    v = re.sub(r"^https?://", "", v)
    v = v.split("/", 1)[0]
    v = v.split("?", 1)[0]
    # Strip leading www.
    if v.startswith("www."):
        v = v[4:]
    return v.strip(". ")


def is_aggregator_domain(domain: str) -> bool:
    """True if the domain is on the aggregator blocklist."""
    d = _extract_domain(domain)
    if not d:
        return False
    if d in AGGREGATOR_DOMAINS:
        return True
    # Match registered root for subdomains (e.g. `m.facebook.com`)
    parts = d.split(".")
    if len(parts) >= 2:
        root = ".".join(parts[-2:])
        if root in AGGREGATOR_DOMAINS:
            return True
        if len(parts) >= 3:
            root3 = ".".join(parts[-3:])  # e.g. en.wikipedia.org
            if root3 in AGGREGATOR_DOMAINS:
                return True
    return False


def classify_email(email: Optional[str]) -> Tuple[str, str]:
    """Classify an email address. Returns (verdict, reason).

    verdicts:
      • "ok"               — looks like a real, business-specific contact
      • "junk-aggregator"  — local@<aggregator> (e.g. info@facebook.com)
      • "junk-role-only"   — generic role-mailbox on a real domain. Still
                             allowed by default; caller decides.
      • "empty"            — missing / not an email
      • "malformed"        — has @ but no parseable domain
    """
    if not email or not isinstance(email, str):
        return ("empty", "empty")
    em = email.strip().lower()
    if "@" not in em:
        return ("malformed", "no-at-sign")
    local, _, domain = em.partition("@")
    domain = _extract_domain(domain)
    if not domain:
        return ("malformed", "no-domain")
    if is_aggregator_domain(domain):
        return ("junk-aggregator", f"aggregator-domain:{domain}")
    if local in _ROLE_LOCALPARTS:
        return ("junk-role-only", f"role-mailbox:{local}@{domain}")
    return ("ok", "")


def is_blastable_email(email: Optional[str]) -> bool:
    """Convenience: True only if the email passes the strictest gate
    (no aggregator junk; role-mailboxes still allowed because most SMBs
    use them)."""
    verdict, _ = classify_email(email)
    return verdict in ("ok", "junk-role-only")
