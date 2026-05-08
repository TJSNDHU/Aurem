/**
 * AUREM Camofox Browser Service
 * Anti-detection browser wrapper for Scout Agent
 * Runs as Express REST API on port 9222
 */
const { execSync } = require('child_process');
const http = require('http');
const { URL } = require('url');

let camoufox;
try {
  camoufox = require('@askjo/camoufox-browser');
} catch (e) {
  console.error('[Camofox] Package not found:', e.message);
}

const PORT = parseInt(process.env.CAMOFOX_PORT || '9222');

let browser = null;

async function getBrowser() {
  if (!browser && camoufox) {
    try {
      browser = await camoufox.launch({ headless: true });
      console.log('[Camofox] Browser launched');
    } catch (e) {
      console.error('[Camofox] Launch error:', e.message);
    }
  }
  return browser;
}

/**
 * Navigate to URL and return page content
 */
async function navigateAndExtract(url, options = {}) {
  const b = await getBrowser();
  if (!b) {
    throw new Error('Camofox browser not available');
  }

  const page = await b.newPage();
  const timeout = options.timeout || 30000;

  try {
    // Set realistic viewport
    await page.setViewportSize({ width: 1920, height: 1080 });

    // Navigate with anti-detection
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout });
    await page.waitForTimeout(2000); // Human-like pause

    // Scroll for lazy-loaded content
    if (options.scroll) {
      for (let i = 0; i < 3; i++) {
        await page.evaluate(() => window.scrollBy(0, window.innerHeight));
        await page.waitForTimeout(800);
      }
      await page.evaluate(() => window.scrollTo(0, 0));
    }

    // Extract content based on type
    let result = {};

    if (options.selector) {
      // Extract specific elements
      result.elements = await page.$$eval(options.selector, els =>
        els.map(el => ({
          text: el.innerText?.trim(),
          href: el.href || '',
          src: el.src || '',
        }))
      );
    }

    if (options.screenshot) {
      result.screenshot = await page.screenshot({ type: 'jpeg', quality: 50 });
    }

    // Always return full text and title
    result.title = await page.title();
    result.url = page.url();
    result.text = await page.evaluate(() => document.body?.innerText || '');
    result.html = options.html ? await page.content() : undefined;

    // Extract structured data if present
    result.structured = await page.evaluate(() => {
      const ldJson = document.querySelectorAll('script[type="application/ld+json"]');
      return Array.from(ldJson).map(s => {
        try { return JSON.parse(s.textContent); } catch { return null; }
      }).filter(Boolean);
    });

    return result;
  } finally {
    await page.close().catch(() => {});
  }
}

/**
 * Google Maps lead extraction
 */
async function extractGoogleMapsLeads(query, location) {
  const searchUrl = `https://www.google.com/maps/search/${encodeURIComponent(query + ' ' + location)}`;
  const b = await getBrowser();
  if (!b) throw new Error('Camofox browser not available');

  const page = await b.newPage();
  try {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(searchUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);

    // Scroll results panel for more listings
    for (let i = 0; i < 5; i++) {
      await page.evaluate(() => {
        const feed = document.querySelector('[role="feed"]');
        if (feed) feed.scrollTop += 500;
      });
      await page.waitForTimeout(1000);
    }

    // Extract business listings
    const leads = await page.evaluate(() => {
      const results = [];
      const items = document.querySelectorAll('[data-result-index], .Nv2PK');
      items.forEach(item => {
        const name = item.querySelector('.qBF1Pd, .fontHeadlineSmall')?.textContent?.trim();
        const rating = item.querySelector('.MW4etd, .ZkP5Je')?.textContent?.trim();
        const reviews = item.querySelector('.UY7F9')?.textContent?.match(/\d+/)?.[0];
        const category = item.querySelector('.W4Efsd:first-child .W4Efsd')?.textContent?.trim();
        const address = item.querySelector('.W4Efsd:nth-child(3)')?.textContent?.trim();
        const phone = item.querySelector('[data-tooltip*="phone"], .UsdlK')?.textContent?.trim();
        const website = item.querySelector('a[data-value="Website"]')?.href;
        if (name) {
          results.push({ name, rating, reviews, category, address, phone, website });
        }
      });
      return results;
    });

    return { leads, total: leads.length, query, location, source: 'google_maps' };
  } finally {
    await page.close().catch(() => {});
  }
}

/**
 * LinkedIn company page scraping
 */
async function scrapeLinkedInCompany(companyUrl) {
  const b = await getBrowser();
  if (!b) throw new Error('Camofox browser not available');

  const page = await b.newPage();
  try {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(companyUrl, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(3000);

    const data = await page.evaluate(() => ({
      name: document.querySelector('.org-top-card-summary__title, h1')?.textContent?.trim(),
      tagline: document.querySelector('.org-top-card-summary__tagline')?.textContent?.trim(),
      industry: document.querySelector('.org-top-card-summary-info-list__info-item')?.textContent?.trim(),
      size: document.querySelector('[data-test-id="about-us__size"]')?.textContent?.trim(),
      description: document.querySelector('.org-about-us-organization-description__text')?.textContent?.trim(),
      website: document.querySelector('.org-about-us-company-module__company-page-url a')?.href,
      followers: document.querySelector('.org-top-card-summary-info-list__info-item:last-child')?.textContent?.trim(),
    }));

    return { ...data, source_url: companyUrl, source: 'linkedin' };
  } finally {
    await page.close().catch(() => {});
  }
}

// ── HTTP Server ──
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  res.setHeader('Content-Type', 'application/json');

  // Health check
  if (url.pathname === '/health') {
    res.end(JSON.stringify({ status: 'ok', browser: !!browser, service: 'camofox' }));
    return;
  }

  // Only POST for actions
  if (req.method !== 'POST') {
    res.statusCode = 405;
    res.end(JSON.stringify({ error: 'POST only' }));
    return;
  }

  let body = '';
  req.on('data', c => body += c);
  req.on('end', async () => {
    try {
      const data = JSON.parse(body || '{}');

      if (url.pathname === '/navigate') {
        const result = await navigateAndExtract(data.url, data.options || {});
        res.end(JSON.stringify({ success: true, ...result }));
      } else if (url.pathname === '/google-maps') {
        const result = await extractGoogleMapsLeads(data.query, data.location);
        res.end(JSON.stringify({ success: true, ...result }));
      } else if (url.pathname === '/linkedin') {
        const result = await scrapeLinkedInCompany(data.url);
        res.end(JSON.stringify({ success: true, ...result }));
      } else {
        res.statusCode = 404;
        res.end(JSON.stringify({ error: 'Not found' }));
      }
    } catch (e) {
      console.error('[Camofox] Error:', e.message);
      res.statusCode = 500;
      res.end(JSON.stringify({ error: e.message }));
    }
  });
});

server.listen(PORT, () => {
  console.log(`[Camofox] REST API running on port ${PORT}`);
  getBrowser(); // Pre-launch browser
});

// Cleanup
process.on('SIGTERM', async () => {
  if (browser) await browser.close().catch(() => {});
  process.exit(0);
});
