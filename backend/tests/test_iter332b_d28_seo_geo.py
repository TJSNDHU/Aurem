"""
iter 332b D-28 — SEO + GEO (Generative Engine Optimization) tests.

These are file-text assertions confirming every public page wires up
the unified `<SEO />` component AND that the static SEO files
(robots.txt, sitemap.xml, llms.txt) carry the right surfaces.
"""
from pathlib import Path


PUBLIC = Path("/app/frontend/public")
PAGES = Path("/app/frontend/src/platform")


# ── 1. Unified SEO component exists with all required surfaces ────────
def test_seo_component_covers_all_surfaces():
    src = (Path("/app/frontend/src/components/SEO.jsx")).read_text()
    for surface in [
        # Core
        "<title>", 'name="description"', 'rel="canonical"', 'name="robots"',
        # Geographic
        'name="geo.region"',
        'name="geo.placename"',
        'name="ICBM"',
        'hrefLang="en-ca"',
        # GEO / Generative
        'name="ai-summary"',
        'name="llm-summary"',
        # Open Graph
        'property="og:type"',
        'property="og:image"',
        'property="og:locale"',
        # Twitter
        'name="twitter:card"',
        # Structured data
        'application/ld+json',
        'Organization',
        'WebSite',
        'BreadcrumbList',
        'FAQPage',
        'SoftwareApplication',
    ]:
        assert surface in src, f"SEO surface missing: {surface}"


# ── 2. Dev pages all wire SEO ─────────────────────────────────────────
def test_dev_pages_wire_seo():
    dev_pages = [
        "developers/DevLanding.jsx",
        "developers/DevLogin.jsx",
        "developers/DevSignup.jsx",
        "developers/DevDashboard.jsx",
        "developers/DevApiDocs.jsx",
        "developers/DevConnect.jsx",
    ]
    for p in dev_pages:
        text = (PAGES / p).read_text()
        assert "import SEO from" in text, f"{p}: SEO import missing"
        assert "<SEO" in text, f"{p}: <SEO /> not rendered"


# ── 3. Homepage wires SEO with FAQ + AI summary ──────────────────────
def test_homepage_wires_seo_with_faq_and_ai_summary():
    text = (PAGES / "AuremHomepage.jsx").read_text()
    assert "import SEO from" in text
    assert "<SEO" in text
    assert "aiSummary=" in text
    assert "faq={" in text
    # Schema for org + site + app present.
    assert '"Organization"' in text
    assert '"WebSite"' in text
    assert '"SoftwareApplication"' in text


# ── 4. robots.txt explicitly allows AI crawlers ──────────────────────
def test_robots_allows_modern_ai_crawlers():
    text = (PUBLIC / "robots.txt").read_text()
    for ua in [
        "User-agent: GPTBot",
        "User-agent: PerplexityBot",
        "User-agent: ClaudeBot",
        "User-agent: Google-Extended",
        "User-agent: OAI-SearchBot",
        "User-agent: CCBot",
        "User-agent: anthropic-ai",
    ]:
        assert ua in text, f"robots.txt missing crawler: {ua}"
    # Authed surfaces excluded.
    assert "Disallow: /my" in text
    assert "Disallow: /admin" in text


# ── 5. sitemap.xml covers public surfaces only ───────────────────────
def test_sitemap_covers_public_surfaces():
    text = (PUBLIC / "sitemap.xml").read_text()
    for loc in [
        "https://aurem.live/",
        "https://aurem.live/developers",
        "https://aurem.live/developers/signup",
        "https://aurem.live/developers/api-docs",
        "https://aurem.live/services",
        "https://aurem.live/pricing",
    ]:
        assert loc in text, f"sitemap missing: {loc}"
    # Authed surfaces NOT in sitemap.
    for bad in ["loc>https://aurem.live/my<",
                "loc>https://aurem.live/admin",
                "loc>https://aurem.live/developers/dashboard"]:
        assert bad not in text, f"sitemap leaks authed surface: {bad}"


# ── 6. llms.txt has rich AI-citation context ─────────────────────────
def test_llms_txt_is_citation_ready():
    text = (PUBLIC / "llms.txt").read_text()
    assert text.startswith("# AUREM")
    # The blockquote summary is the canonical fact-dense line LLMs cite.
    assert "> AUREM" in text
    assert "PIPEDA" in text
    assert "Canadian" in text
    # Key product surfaces listed.
    assert "/my" in text and "/developers" in text
    # Disambiguation paragraph helps AI tell us apart from "aurum".
    assert "Polaris Built Inc." in text
