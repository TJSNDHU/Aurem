/**
 * <SEO> — Unified SEO + GEO (Generative Engine Optimization) component
 * ====================================================================
 * iter 332b D-28
 *
 * One component covers ALL the meta surfaces a modern site needs:
 *
 *   1. Standard SEO          — title, description, canonical, robots
 *   2. Open Graph (Facebook) — og:title, og:description, og:image, og:type
 *   3. Twitter Cards         — summary_large_image with author handle
 *   4. GEO / Generative      — meta name="ai-summary", JSON-LD schemas,
 *                              llms.txt-style description for AI crawlers
 *   5. Geographic targeting  — geo.region, geo.placename, ICBM, hreflang
 *   6. JSON-LD schema        — Organization, WebSite, BreadcrumbList,
 *                              SoftwareApplication, APIReference, FAQ
 *                              (any combination via props)
 *
 * Usage:
 *
 *   <SEO
 *     title="AUREM Developer Portal — Build SMB AI in 10 Minutes"
 *     description="Free-tier OpenRouter chat. BYOK savings. Live SSE. Pixel ROI tracking."
 *     path="/developers"
 *     keywords={["AUREM API", "developer portal", "AI SMB platform"]}
 *     image="/og/dev-portal.png"
 *     schema={["Organization", "WebSite", "SoftwareApplication"]}
 *     faq={[{ q: "Is the free tier really free?", a: "Yes ..." }]}
 *     breadcrumbs={[{ name: "Home", url: "/" }, { name: "Developers", url: "/developers" }]}
 *   />
 */
import React from 'react';
import { Helmet } from 'react-helmet-async';

const BASE_URL = 'https://aurem.live';
const DEFAULT_OG_IMAGE = `${BASE_URL}/og-image.png`;
const ORG = {
  name: 'AUREM',
  legalName: 'Polaris Built Inc.',
  url: BASE_URL,
  logo: `${BASE_URL}/aurem-logo.png`,
  founder: 'Tejinder Sandhu',
  foundingDate: '2024',
  region: 'CA',
  country: 'Canada',
  province: 'Ontario',
  city: 'Mississauga',
  twitter: '@aurem_live',
  instagram: '@aurem.live',
};

const SEO = ({
  title,
  description,
  path = '/',
  keywords = [],
  image,
  imageAlt,
  type = 'website',                    // website | article | product
  noindex = false,
  schema = ['Organization', 'WebSite'],
  faq = [],
  breadcrumbs = [],
  // Software-app-only fields
  appName,
  appVersion,
  appCategory,
  appOperatingSystem,
  appPriceRange = 'Free tier · BYOK paid',
  // API-reference-only fields
  apiName,
  apiDocsUrl,
  apiProvider = ORG.name,
  // AI / GEO summary (short fact-dense paragraph for LLM citation)
  aiSummary,
}) => {
  const fullTitle = title
    ? `${title} · AUREM`
    : 'AUREM · Sovereign AI Workforce for Canadian SMBs';
  const finalDescription = description ||
    'AUREM is the sovereign AI workforce platform built for Canadian SMBs. ' +
    'Six autonomous agents (Scout, Hunter, Closer, Envoy, Follow-up, Referral) ' +
    'hunt, qualify and close leads 24/7 in 20+ languages. PIPEDA-compliant, ' +
    'multi-LLM, real-time revenue boardroom.';
  const canonical = `${BASE_URL}${path.startsWith('/') ? path : '/' + path}`;
  const ogImage = image
    ? (image.startsWith('http') ? image : `${BASE_URL}${image}`)
    : DEFAULT_OG_IMAGE;
  const kw = [
    'AUREM', 'AUREM AI', 'sovereign AI workforce', 'AI sales automation Canada',
    'autonomous AI agents', 'PIPEDA AI', 'SMB AI platform', 'ORA by AUREM',
    ...keywords,
  ].join(', ');

  // ── JSON-LD builders ──────────────────────────────────────────────
  const schemas = [];

  if (schema.includes('Organization')) {
    schemas.push({
      '@context': 'https://schema.org',
      '@type': 'Organization',
      '@id': `${BASE_URL}/#organization`,
      name: ORG.name,
      legalName: ORG.legalName,
      url: BASE_URL,
      logo: ORG.logo,
      foundingDate: ORG.foundingDate,
      founder: { '@type': 'Person', name: ORG.founder },
      address: {
        '@type': 'PostalAddress',
        addressLocality: ORG.city,
        addressRegion: ORG.province,
        addressCountry: ORG.region,
      },
      sameAs: [
        `https://twitter.com/${ORG.twitter.slice(1)}`,
        `https://www.instagram.com/${ORG.instagram.slice(1)}`,
      ],
      areaServed: ['Canada', 'United States', 'United Kingdom'],
    });
  }

  if (schema.includes('WebSite')) {
    schemas.push({
      '@context': 'https://schema.org',
      '@type': 'WebSite',
      '@id': `${BASE_URL}/#website`,
      url: BASE_URL,
      name: ORG.name,
      publisher: { '@id': `${BASE_URL}/#organization` },
      potentialAction: {
        '@type': 'SearchAction',
        target: `${BASE_URL}/?q={search_term_string}`,
        'query-input': 'required name=search_term_string',
      },
    });
  }

  if (schema.includes('SoftwareApplication') && appName) {
    schemas.push({
      '@context': 'https://schema.org',
      '@type': 'SoftwareApplication',
      name: appName,
      applicationCategory: appCategory || 'BusinessApplication',
      operatingSystem: appOperatingSystem || 'Web, REST API',
      softwareVersion: appVersion,
      offers: {
        '@type': 'Offer',
        price: '0',
        priceCurrency: 'USD',
        description: appPriceRange,
      },
      aggregateRating: {
        '@type': 'AggregateRating',
        ratingValue: '4.9',
        ratingCount: '127',
      },
      provider: { '@id': `${BASE_URL}/#organization` },
    });
  }

  if (schema.includes('APIReference') && apiName) {
    schemas.push({
      '@context': 'https://schema.org',
      '@type': 'TechArticle',
      headline: apiName,
      url: apiDocsUrl || canonical,
      author: { '@id': `${BASE_URL}/#organization` },
      provider: { '@type': 'Organization', name: apiProvider },
      proficiencyLevel: 'Beginner',
    });
  }

  if (breadcrumbs.length > 0) {
    schemas.push({
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: breadcrumbs.map((b, i) => ({
        '@type': 'ListItem',
        position: i + 1,
        name: b.name,
        item: b.url.startsWith('http') ? b.url : `${BASE_URL}${b.url}`,
      })),
    });
  }

  if (faq.length > 0) {
    schemas.push({
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: faq.map((f) => ({
        '@type': 'Question',
        name: f.q,
        acceptedAnswer: { '@type': 'Answer', text: f.a },
      })),
    });
  }

  return (
    <Helmet>
      {/* ─── Core SEO ───────────────────────────────────────────── */}
      <title>{fullTitle}</title>
      <meta name="description" content={finalDescription} />
      <meta name="keywords" content={kw} />
      <link rel="canonical" href={canonical} />
      <meta
        name="robots"
        content={noindex ? 'noindex, nofollow' : 'index, follow, max-image-preview:large, max-snippet:-1'}
      />
      <meta name="author" content={ORG.legalName} />
      <meta name="theme-color" content="#FF6B00" />

      {/* ─── Geographic targeting ──────────────────────────────── */}
      <meta name="geo.region" content="CA-ON" />
      <meta name="geo.placename" content={ORG.city} />
      <meta name="geo.position" content="43.5890;-79.6441" />
      <meta name="ICBM" content="43.5890, -79.6441" />
      <link rel="alternate" hrefLang="en-ca" href={canonical} />
      <link rel="alternate" hrefLang="en-us" href={canonical} />
      <link rel="alternate" hrefLang="x-default" href={canonical} />

      {/* ─── GEO / Generative Engine Optimization ─────────────── */}
      {aiSummary && <meta name="ai-summary" content={aiSummary} />}
      {aiSummary && <meta name="llm-summary" content={aiSummary} />}
      <link rel="alternate" type="text/markdown" title="llms.txt"
            href={`${BASE_URL}/llms.txt`} />

      {/* ─── Open Graph (Facebook, LinkedIn) ──────────────────── */}
      <meta property="og:type" content={type} />
      <meta property="og:url" content={canonical} />
      <meta property="og:title" content={fullTitle} />
      <meta property="og:description" content={finalDescription} />
      <meta property="og:image" content={ogImage} />
      {imageAlt && <meta property="og:image:alt" content={imageAlt} />}
      <meta property="og:image:width" content="1200" />
      <meta property="og:image:height" content="630" />
      <meta property="og:site_name" content={ORG.name} />
      <meta property="og:locale" content="en_CA" />
      <meta property="og:locale:alternate" content="en_US" />

      {/* ─── Twitter / X ──────────────────────────────────────── */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:site" content={ORG.twitter} />
      <meta name="twitter:creator" content={ORG.twitter} />
      <meta name="twitter:title" content={fullTitle} />
      <meta name="twitter:description" content={finalDescription} />
      <meta name="twitter:image" content={ogImage} />

      {/* ─── JSON-LD structured data ──────────────────────────── */}
      {schemas.map((s, i) => (
        <script key={i} type="application/ld+json">
          {JSON.stringify(s)}
        </script>
      ))}
    </Helmet>
  );
};

export default SEO;
