/**
 * AUREM Lead Scraper — Content Script
 * Detects page type and extracts lead information
 */

(() => {
  const EMAIL_RE = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/g;
  const PHONE_RE = /(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}/g;

  function detectPageType() {
    const host = window.location.hostname.toLowerCase();
    if (host.includes('linkedin.com')) return 'linkedin';
    if (host.includes('facebook.com') || host.includes('fb.com')) return 'facebook';
    if (host.includes('instagram.com')) return 'instagram';
    if (host.includes('twitter.com') || host.includes('x.com')) return 'twitter';
    if (host.includes('youtube.com')) return 'youtube';
    return 'general';
  }

  function cleanText(el) {
    return el ? el.innerText.trim().replace(/\s+/g, ' ') : '';
  }

  function extractEmails(text) {
    const matches = text.match(EMAIL_RE) || [];
    return [...new Set(matches)].filter(e => !e.endsWith('.png') && !e.endsWith('.jpg'));
  }

  function extractPhones(text) {
    const matches = text.match(PHONE_RE) || [];
    return [...new Set(matches)].filter(p => p.replace(/\D/g, '').length >= 7);
  }

  // ── LinkedIn Scraper ──
  function scrapeLinkedIn() {
    const leads = [];
    const url = window.location.href;

    // Profile page
    if (url.includes('/in/')) {
      const name = cleanText(document.querySelector('.text-heading-xlarge, h1.inline.t-24'));
      const title = cleanText(document.querySelector('.text-body-medium, .pv-text-details__right-panel .text-body-medium'));
      const company = cleanText(document.querySelector('.pv-text-details__right-panel span[aria-hidden="true"]'));
      const location = cleanText(document.querySelector('.text-body-small.inline.t-black--light'));
      const about = cleanText(document.querySelector('#about ~ .display-flex .inline-show-more-text, .pv-about__summary-text'));
      const bodyText = document.body.innerText;
      const emails = extractEmails(bodyText);
      const phones = extractPhones(bodyText);

      if (name) {
        leads.push({
          name: name,
          title: title || '',
          company: company || '',
          location: location || '',
          email: emails[0] || '',
          phone: phones[0] || '',
          about: about.substring(0, 200),
          source_url: url,
          source: 'linkedin_profile'
        });
      }
    }

    // Search results / People list
    const cards = document.querySelectorAll('.reusable-search__result-container, .entity-result, li.reusable-search__result-container');
    cards.forEach(card => {
      const nameEl = card.querySelector('.entity-result__title-text a span[aria-hidden="true"], .app-aware-link span[aria-hidden="true"]');
      const titleEl = card.querySelector('.entity-result__primary-subtitle, .entity-result__summary');
      const locEl = card.querySelector('.entity-result__secondary-subtitle');
      const name = cleanText(nameEl);
      if (name && name !== 'LinkedIn Member') {
        leads.push({
          name: name,
          title: cleanText(titleEl) || '',
          company: '',
          location: cleanText(locEl) || '',
          email: '',
          phone: '',
          source_url: url,
          source: 'linkedin_search'
        });
      }
    });

    // Connections list
    const connCards = document.querySelectorAll('.mn-connection-card');
    connCards.forEach(card => {
      const name = cleanText(card.querySelector('.mn-connection-card__name'));
      const occ = cleanText(card.querySelector('.mn-connection-card__occupation'));
      if (name) {
        leads.push({ name, title: occ, company: '', location: '', email: '', phone: '', source_url: url, source: 'linkedin_connections' });
      }
    });

    return leads;
  }

  // ── Facebook Scraper ──
  function scrapeFacebook() {
    const leads = [];
    const url = window.location.href;
    const bodyText = document.body.innerText;
    const emails = extractEmails(bodyText);
    const phones = extractPhones(bodyText);

    // Page info
    const pageName = cleanText(document.querySelector('h1, [role="heading"][aria-level="1"]'));
    if (pageName) {
      leads.push({
        name: pageName,
        title: 'Facebook Page',
        company: pageName,
        email: emails[0] || '',
        phone: phones[0] || '',
        source_url: url,
        source: 'facebook_page'
      });
    }

    return leads;
  }

  // ── Instagram Scraper ──
  function scrapeInstagram() {
    const leads = [];
    const url = window.location.href;
    const bodyText = document.body.innerText;
    const emails = extractEmails(bodyText);

    const nameEl = document.querySelector('header h2, header h1');
    const bioEl = document.querySelector('header section > div.-vDIg span, header section h1 + div');
    const name = cleanText(nameEl);
    
    if (name) {
      leads.push({
        name: name,
        title: cleanText(bioEl) || 'Instagram Profile',
        company: '',
        email: emails[0] || '',
        phone: '',
        source_url: url,
        source: 'instagram_profile'
      });
    }
    return leads;
  }

  // ── General Web Scraper ──
  function scrapeGeneral() {
    const leads = [];
    const url = window.location.href;
    const bodyText = document.body.innerText;
    const emails = extractEmails(bodyText);
    const phones = extractPhones(bodyText);
    const pageTitle = document.title || window.location.hostname;

    // Extract from contact sections, about pages, team pages
    const contactSections = document.querySelectorAll(
      '[class*="contact"], [class*="team"], [class*="about"], [id*="contact"], [id*="team"], footer'
    );
    
    let contactText = '';
    contactSections.forEach(s => contactText += ' ' + s.innerText);
    const contactEmails = extractEmails(contactText);
    const contactPhones = extractPhones(contactText);

    // Merge unique
    const allEmails = [...new Set([...contactEmails, ...emails])];
    const allPhones = [...new Set([...contactPhones, ...phones])];

    // Create lead per email found, or one general lead
    if (allEmails.length > 0) {
      allEmails.forEach(email => {
        leads.push({
          name: pageTitle,
          title: 'Website Contact',
          company: window.location.hostname.replace('www.', ''),
          email: email,
          phone: allPhones[0] || '',
          source_url: url,
          source: 'website'
        });
      });
    } else if (allPhones.length > 0) {
      leads.push({
        name: pageTitle,
        title: 'Website Contact',
        company: window.location.hostname.replace('www.', ''),
        email: '',
        phone: allPhones[0],
        source_url: url,
        source: 'website'
      });
    }

    // Try to find structured data (Schema.org)
    const ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
    ldScripts.forEach(script => {
      try {
        const data = JSON.parse(script.textContent);
        if (data.email || data.telephone) {
          leads.push({
            name: data.name || pageTitle,
            title: data.jobTitle || data['@type'] || 'Structured Data',
            company: data.worksFor?.name || data.name || '',
            email: data.email || '',
            phone: data.telephone || '',
            source_url: url,
            source: 'schema_org'
          });
        }
      } catch {}
    });

    return leads;
  }

  // ── Main scrape handler ──
  function scrapeCurrentPage() {
    const pageType = detectPageType();
    let leads = [];

    switch (pageType) {
      case 'linkedin': leads = scrapeLinkedIn(); break;
      case 'facebook': leads = scrapeFacebook(); break;
      case 'instagram': leads = scrapeInstagram(); break;
      default: leads = scrapeGeneral(); break;
    }

    // Deduplicate by name+email
    const seen = new Set();
    leads = leads.filter(l => {
      const key = `${l.name}|${l.email}`.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    return { pageType, url: window.location.href, title: document.title, leads, scrapedAt: new Date().toISOString() };
  }

  // Listen for messages from popup
  chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
    if (msg.action === 'scrape') {
      const result = scrapeCurrentPage();
      sendResponse(result);
    }
    if (msg.action === 'ping') {
      sendResponse({ ready: true });
    }
    return true;
  });
})();
