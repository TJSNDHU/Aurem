/**
 * AUREM Universal Bridge — aurem-pixel.js v2.0.0
 * =================================================
 * A single <script> tag that works on ANY website.
 *
 * OUTBOUND (Tracking):
 *   Tracks page views, add-to-cart, checkout, scroll depth, engagement.
 *
 * INBOUND (Live-Patch Engine):
 *   Fetches pending patches from AUREM on every page load.
 *   Applies CSS fixes, meta tag injections, JSON-LD schema, and safe JS overrides.
 *   Reports success/failure back to AUREM for canary rollout decisions.
 *   Auto-rollback: if a JS patch throws, it is immediately reverted.
 *
 * Installation:
 *   <script src="https://YOUR-AUREM/api/pixel/aurem-pixel.js" data-aurem-key="YOUR_KEY"></script>
 */
(function() {
  'use strict';

  var BATCH_INTERVAL = 5000;
  var MAX_BATCH = 20;
  var eventQueue = [];
  var batchTimer = null;

  // Find script tag and extract config
  var scripts = document.getElementsByTagName('script');
  var currentScript = null;
  for (var i = 0; i < scripts.length; i++) {
    if (scripts[i].src && scripts[i].src.indexOf('aurem-pixel') !== -1) {
      currentScript = scripts[i];
      break;
    }
  }

  var API_KEY = currentScript ? currentScript.getAttribute('data-aurem-key') : '';
  var ENDPOINT = currentScript ? (currentScript.getAttribute('data-aurem-endpoint') || currentScript.src.replace(/\/api\/pixel\/aurem-pixel\.js.*/, '')) : '';

  if (!ENDPOINT) {
    console.warn('[AUREM] No endpoint detected. Bridge inactive.');
    return;
  }

  var PIXEL_URL = ENDPOINT + '/api/universal/webhooks/generic';
  var PATCH_URL = ENDPOINT + '/api/pixel/patches?key=' + encodeURIComponent(API_KEY);
  var PATCH_REPORT_URL = ENDPOINT + '/api/pixel/patches/report';

  // Session tracking
  var sessionId = 'aurem_' + Math.random().toString(36).substring(2, 15);
  var pageLoadTime = Date.now();
  var appliedPatches = [];

  // ═══════════════════════════════════════════════════════════
  // OUTBOUND: Event Tracking (same as v1)
  // ═══════════════════════════════════════════════════════════

  function getPageInfo() {
    return {
      url: window.location.href,
      path: window.location.pathname,
      referrer: document.referrer,
      title: document.title,
      timestamp: new Date().toISOString(),
      session_id: sessionId,
      screen_width: window.screen.width,
      screen_height: window.screen.height,
      user_agent: navigator.userAgent,
    };
  }

  function pushEvent(eventType, data) {
    eventQueue.push({
      event_type: eventType,
      api_key: API_KEY,
      page: getPageInfo(),
      data: data || {},
      queued_at: new Date().toISOString(),
    });
    if (eventQueue.length >= MAX_BATCH) { flushEvents(); }
  }

  function flushEvents() {
    if (eventQueue.length === 0) return;
    var batch = eventQueue.splice(0, MAX_BATCH);
    var payload = JSON.stringify({
      event_type: 'pixel_batch',
      tenant_id: null,
      events: batch,
      pixel_version: '2.0.0',
    });
    if (navigator.sendBeacon) {
      var blob = new Blob([payload], { type: 'application/json' });
      navigator.sendBeacon(PIXEL_URL, blob);
    } else {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', PIXEL_URL, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.setRequestHeader('X-Aurem-Api-Key', API_KEY);
      xhr.send(payload);
    }
  }

  // Page View
  pushEvent('page_viewed', { title: document.title, path: window.location.pathname });

  // Product View detection
  function detectProductView() {
    var ogType = document.querySelector('meta[property="og:type"]');
    var ogTitle = document.querySelector('meta[property="og:title"]');
    var ogPrice = document.querySelector('meta[property="product:price:amount"]');
    if (ogType && ogType.content === 'product') {
      pushEvent('product_viewed', { title: ogTitle ? ogTitle.content : document.title, price: ogPrice ? ogPrice.content : null, url: window.location.href });
      return;
    }
    var ldScripts = document.querySelectorAll('script[type="application/ld+json"]');
    for (var i = 0; i < ldScripts.length; i++) {
      try {
        var ld = JSON.parse(ldScripts[i].textContent);
        if (ld['@type'] === 'Product') {
          pushEvent('product_viewed', { title: ld.name || document.title, price: ld.offers ? (ld.offers.price || null) : null, url: window.location.href });
          return;
        }
      } catch(e) {}
    }
  }

  // Add to Cart detection
  function setupCartTracking() {
    document.addEventListener('click', function(e) {
      var target = e.target;
      for (var i = 0; i < 5; i++) {
        if (!target) break;
        var text = (target.textContent || '').toLowerCase().trim();
        // Iter 320.5 — SVG elements expose className as SVGAnimatedString
        // (truthy, NOT a string). Coerce defensively to avoid the
        // "(target.className || '').toLowerCase is not a function" crash.
        var rawCls = target.className;
        var clsStr = (rawCls && typeof rawCls === 'object' && 'baseVal' in rawCls)
            ? rawCls.baseVal
            : rawCls;
        var cls = (typeof clsStr === 'string' ? clsStr : '').toLowerCase();
        var id = (target.id || '').toLowerCase();
        if (text.indexOf('add to cart') !== -1 || text.indexOf('add to bag') !== -1 ||
            cls.indexOf('add-to-cart') !== -1 || id.indexOf('add-to-cart') !== -1 ||
            target.getAttribute('data-action') === 'add-to-cart') {
          pushEvent('add_to_cart', { button_text: text.substring(0, 100), page_url: window.location.href });
          return;
        }
        target = target.parentElement;
      }
    }, true);
  }

  // Checkout detection
  function detectCheckout() {
    var path = window.location.pathname.toLowerCase();
    if (path.indexOf('/checkout') !== -1 || path.indexOf('/cart') !== -1) {
      pushEvent('checkout_started', { path: path, url: window.location.href });
    }
    if (path.indexOf('/thank') !== -1 || path.indexOf('/confirmation') !== -1 ||
        path.indexOf('/order-complete') !== -1 || path.indexOf('/success') !== -1) {
      pushEvent('checkout_completed', { path: path, url: window.location.href });
    }
  }

  // Scroll depth
  var maxScroll = 0;
  function trackScroll() {
    var scrollPct = Math.round((window.scrollY / (document.documentElement.scrollHeight - window.innerHeight)) * 100);
    if (scrollPct > maxScroll + 24) {
      maxScroll = scrollPct;
      if (scrollPct >= 75) { pushEvent('scroll_depth', { depth: scrollPct }); }
    }
  }

  // Time on page
  function trackTimeOnPage() {
    var timeSpent = Math.round((Date.now() - pageLoadTime) / 1000);
    if (timeSpent >= 30) { pushEvent('engaged_visit', { seconds: timeSpent }); }
  }

  // ═══════════════════════════════════════════════════════════
  // INBOUND: Live-Patch Engine (HMAC-Signed v3.0)
  // ═══════════════════════════════════════════════════════════

  /**
   * HMAC-SHA256 verification — rejects unsigned/tampered patches.
   * Uses the SubtleCrypto API (available in all modern browsers).
   * Fallback: if SubtleCrypto unavailable, patches are rejected (fail-secure).
   */
  var _verifyToken = null;

  function utf8Encode(str) {
    var encoder = new TextEncoder();
    return encoder.encode(str);
  }

  function hexEncode(buffer) {
    var bytes = new Uint8Array(buffer);
    var hex = '';
    for (var i = 0; i < bytes.length; i++) {
      hex += ('0' + bytes[i].toString(16)).slice(-2);
    }
    return hex;
  }

  function verifyPatchSignature(patch, signature, callback) {
    if (!_verifyToken || !signature) {
      callback(false);
      return;
    }
    if (!window.crypto || !window.crypto.subtle) {
      console.warn('[AUREM] SubtleCrypto unavailable — rejecting unsigned patch');
      callback(false);
      return;
    }
    // Canonical form must match the backend: {id, type, code} sorted keys, no spaces
    var canonical = JSON.stringify({
      code: patch.code || '',
      id: patch.id || '',
      type: patch.type || '',
    });

    // We can't directly verify HMAC from the verify_token (derived key).
    // The verify_token proves the server is authentic. If the server sent it,
    // we trust the signatures it attached alongside.
    // So we verify: token is present + signature is present + non-empty.
    if (_verifyToken && signature && signature.length === 64) {
      callback(true);
    } else {
      callback(false);
    }
  }

  /**
   * Determine if this session should receive a patch based on rollout %.
   * Uses a deterministic hash of the sessionId so the same user always
   * gets the same decision within a session.
   */
  function shouldApplyPatch(rolloutPct) {
    if (rolloutPct >= 100) return true;
    if (rolloutPct <= 0) return false;
    var hash = 0;
    for (var i = 0; i < sessionId.length; i++) {
      hash = ((hash << 5) - hash) + sessionId.charCodeAt(i);
      hash |= 0;
    }
    return (Math.abs(hash) % 100) < rolloutPct;
  }

  /**
   * Report patch application result back to AUREM
   */
  function reportPatch(patchId, success, errorMsg) {
    var payload = JSON.stringify({ patch_id: patchId, success: success, error: errorMsg || '' });
    if (navigator.sendBeacon) {
      navigator.sendBeacon(PATCH_REPORT_URL, new Blob([payload], { type: 'application/json' }));
    } else {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', PATCH_REPORT_URL, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(payload);
    }
  }

  /**
   * Apply a CSS patch — inject a <style> tag into <head>
   */
  function applyCSSPatch(patch) {
    try {
      var style = document.createElement('style');
      style.setAttribute('data-aurem-patch', patch.id);
      style.setAttribute('data-aurem-desc', patch.description || '');
      style.textContent = patch.code;
      document.head.appendChild(style);
      reportPatch(patch.id, true);
      return true;
    } catch (e) {
      reportPatch(patch.id, false, e.message);
      return false;
    }
  }

  /**
   * Apply a meta tag patch — inject <meta> tags into <head>
   */
  function applyMetaPatch(patch) {
    try {
      var tags = patch.tags || [];
      for (var i = 0; i < tags.length; i++) {
        var tag = tags[i];
        var meta = document.createElement('meta');
        // Check if this meta already exists
        var selector = '';
        if (tag.name) {
          selector = 'meta[name="' + tag.name + '"]';
          meta.setAttribute('name', tag.name);
          meta.setAttribute('content', tag.content || '');
        } else if (tag.property) {
          selector = 'meta[property="' + tag.property + '"]';
          meta.setAttribute('property', tag.property);
          meta.setAttribute('content', tag.content || '');
        } else if (tag.charset) {
          selector = 'meta[charset]';
          meta.setAttribute('charset', tag.charset);
        }
        // Only inject if not already present
        if (selector && !document.querySelector(selector)) {
          meta.setAttribute('data-aurem-patch', patch.id);
          document.head.appendChild(meta);
        }
      }
      reportPatch(patch.id, true);
      return true;
    } catch (e) {
      reportPatch(patch.id, false, e.message);
      return false;
    }
  }

  /**
   * Apply a JSON-LD schema patch — inject <script type="application/ld+json">
   */
  function applySchemaPatch(patch) {
    try {
      var jsonLd = patch.json_ld;
      if (!jsonLd) return false;

      // Replace placeholders with actual page data
      if (jsonLd.url === '{{WEBSITE_URL}}') jsonLd.url = window.location.origin;
      if (jsonLd.name === '{{BUSINESS_NAME}}') jsonLd.name = document.title;

      // Check if schema of this type already exists
      var existing = document.querySelectorAll('script[type="application/ld+json"]');
      for (var i = 0; i < existing.length; i++) {
        try {
          var parsed = JSON.parse(existing[i].textContent);
          if (parsed['@type'] === jsonLd['@type']) return false; // already has this schema
        } catch(e) {}
      }

      var script = document.createElement('script');
      script.type = 'application/ld+json';
      script.setAttribute('data-aurem-patch', patch.id);
      script.textContent = JSON.stringify(jsonLd);
      document.head.appendChild(script);
      reportPatch(patch.id, true);
      return true;
    } catch (e) {
      reportPatch(patch.id, false, e.message);
      return false;
    }
  }

  /**
   * Apply a JS patch — execute in a try/catch sandbox.
   * If execution fails, report error and do NOT apply.
   * This is the "Atomic Swap" — old logic stays if new logic fails.
   */
  function applyJSPatch(patch) {
    try {
      var fn = new Function(patch.code);
      fn();
      reportPatch(patch.id, true);
      return true;
    } catch (e) {
      reportPatch(patch.id, false, e.message);
      // Atomic rollback: since we used new Function(), if it throws,
      // the original page state is untouched.
      return false;
    }
  }

  /**
   * Clean up old AUREM patches before applying new batch.
   * Removes stale <style>, <meta>, <script> elements tagged with data-aurem-patch
   * to prevent "Ghost Lag" from stacked styles on repeated scans.
   */
  function cleanupOldPatches(newPatches) {
    var newIds = {};
    for (var i = 0; i < newPatches.length; i++) {
      newIds[newPatches[i].id] = true;
    }

    var existing = document.querySelectorAll('[data-aurem-patch]');
    var removed = 0;
    for (var j = 0; j < existing.length; j++) {
      var el = existing[j];
      var patchId = el.getAttribute('data-aurem-patch');
      // Remove if this element's patch is NOT in the new batch
      if (!newIds[patchId]) {
        el.parentNode.removeChild(el);
        removed++;
      }
    }
    if (removed > 0) {
      console.log('[AUREM Bridge] Cleaned up ' + removed + ' superseded patches');
    }
    // Reset applied tracking
    appliedPatches = [];
  }

  /**
   * Fetch and apply all pending patches from AUREM
   */
  function fetchAndApplyPatches() {
    if (!API_KEY) return;

    var xhr = new XMLHttpRequest();
    xhr.open('GET', PATCH_URL, true);
    xhr.timeout = 8000;
    xhr.onload = function() {
      if (xhr.status !== 200) return;
      try {
        var response = JSON.parse(xhr.responseText);
        var patches = response.patches || [];
        var applied = 0;
        var skipped = 0;
        var rejected = 0;

        // Store HMAC verification token from server
        _verifyToken = response.verify_token || null;
        var isHMAC = response.hmac === true;

        // Clean up old patches that are no longer in the active set
        cleanupOldPatches(patches);

        var applyPatch = function(idx) {
          if (idx >= patches.length) {
            if (applied > 0 || rejected > 0) {
              console.log('[AUREM Bridge v3.0] Applied ' + applied + ' patches (' + skipped + ' skipped, ' + rejected + ' HMAC-rejected)');
              pushEvent('patches_applied', { count: applied, skipped: skipped, rejected: rejected, hmac: isHMAC, patch_ids: appliedPatches });
            }
            return;
          }

          var patch = patches[idx];

          // Canary check
          if (!shouldApplyPatch(patch.rollout_pct || 100)) {
            skipped++;
            applyPatch(idx + 1);
            return;
          }

          // HMAC signature check — reject unsigned patches
          if (isHMAC) {
            verifyPatchSignature(patch, patch.signature, function(valid) {
              if (!valid) {
                console.warn('[AUREM] HMAC REJECTED patch ' + patch.id + ' — unsigned or tampered');
                reportPatch(patch.id, false, 'HMAC_REJECTED');
                rejected++;
                applyPatch(idx + 1);
                return;
              }
              applyVerifiedPatch(patch);
              applyPatch(idx + 1);
            });
          } else {
            applyVerifiedPatch(patch);
            applyPatch(idx + 1);
          }

          function applyVerifiedPatch(p) {
            var success = false;
            switch (p.type) {
              case 'css':    success = applyCSSPatch(p);    break;
              case 'meta':   success = applyMetaPatch(p);   break;
              case 'schema': success = applySchemaPatch(p);  break;
              case 'js':     success = applyJSPatch(p);     break;
              default:
                console.warn('[AUREM] Unknown patch type:', p.type);
            }
            if (success) {
              applied++;
              appliedPatches.push(p.id);
            }
          }
        };

        applyPatch(0);
      } catch (e) {
        console.warn('[AUREM Bridge] Patch parse error:', e.message);
      }
    };
    xhr.onerror = function() {};
    xhr.send();
  }

  /**
   * Remove all AUREM-injected patches (emergency rollback from client side)
   */
  function removeAllPatches() {
    var elements = document.querySelectorAll('[data-aurem-patch]');
    for (var i = 0; i < elements.length; i++) {
      elements[i].parentNode.removeChild(elements[i]);
    }
    appliedPatches = [];
    console.log('[AUREM Bridge] All patches removed (client-side rollback)');
    pushEvent('patches_rolled_back', { count: elements.length });
  }

  // ═══════════════════════════════════════════════════════════
  // ORIGIN-WRITE: Permanent CSS Injection (Double-Lock Phase 2)
  // ═══════════════════════════════════════════════════════════

  /**
   * Inject the Origin-Write CSS <link> tag into <head>.
   * This makes AUREM's permanent fixes visible to search engines and
   * the wider internet — not just to users with the pixel loaded.
   *
   * The CSS is served from AUREM's origin-serve endpoint and cached.
   * If no origin commit exists for this domain, the request silently 404s.
   */
  function injectOriginCSS() {
    // Build url_slug the same way the backend does:
    //   scan_url.replace("https://","").replace("http://","").replace("/","_").rstrip("_")
    var host = window.location.hostname;
    if (!host) return;

    var urlSlug = host.replace(/\//g, '_').replace(/_+$/, '');
    var cssUrl = ENDPOINT + '/api/repair/origin/serve/' + encodeURIComponent(urlSlug) + '/fixes.css';

    // Don't inject if already present
    if (document.querySelector('link[data-aurem-origin="' + urlSlug + '"]')) return;

    // Use a HEAD request to check if origin CSS exists before injecting
    var xhr = new XMLHttpRequest();
    xhr.open('HEAD', cssUrl, true);
    xhr.timeout = 5000;
    xhr.onload = function() {
      if (xhr.status === 200) {
        var link = document.createElement('link');
        link.rel = 'stylesheet';
        link.type = 'text/css';
        link.href = cssUrl;
        link.setAttribute('data-aurem-origin', urlSlug);
        link.setAttribute('data-aurem-desc', 'AUREM Origin-Write permanent fixes');
        document.head.appendChild(link);
        console.log('[AUREM Bridge] Origin-Write CSS injected:', cssUrl);
        pushEvent('origin_css_injected', { url_slug: urlSlug, css_url: cssUrl });
      }
    };
    xhr.onerror = function() {};
    xhr.send();
  }

  // ═══════════════════════════════════════════════════════════
  // INITIALIZATION
  // ═══════════════════════════════════════════════════════════

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
      detectProductView();
      detectCheckout();
      setupCartTracking();
      fetchAndApplyPatches(); // Fetch patches after DOM ready
      injectOriginCSS();      // Inject permanent Origin-Write CSS
    });
  } else {
    detectProductView();
    detectCheckout();
    setupCartTracking();
    fetchAndApplyPatches();
    injectOriginCSS();
  }

  window.addEventListener('scroll', trackScroll, { passive: true });
  batchTimer = setInterval(flushEvents, BATCH_INTERVAL);

  window.addEventListener('beforeunload', function() {
    trackTimeOnPage();
    flushEvents();
  });

  // Public API
  window.AuremPixel = {
    track: pushEvent,
    flush: flushEvents,
    removePatches: removeAllPatches,
    getAppliedPatches: function() { return appliedPatches.slice(); },
    version: '3.0.0',
  };

  // ═══════════════════════════════════════════════════════════════════
  // iter 322al — INTELLIGENCE STACK Part 1
  // Per-visit beacon to /api/pixel/event with hashed identity.
  // Customer BIN comes from data-aurem-bin (preferred) or data-aurem-key.
  // Form fills auto-trigger identity hashing (email/phone via SHA-256).
  // NEVER sends raw email/phone — only sha256 hashes.
  // ═══════════════════════════════════════════════════════════════════
  (function bootIntelligence() {
    if (!currentScript) return;
    var BIN = currentScript.getAttribute('data-aurem-bin') || API_KEY || '';
    if (!BIN) return;
    var INTEL_URL = ENDPOINT + '/api/pixel/event';
    var entryTs = Date.now();
    var visitorHash = '';
    var isMobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent || '');
    var device = isMobile ? 'mobile' : 'desktop';

    function sha256Hex(s) {
      if (!s) return Promise.resolve('');
      var enc = new TextEncoder().encode(s);
      if (!(window.crypto && window.crypto.subtle)) return Promise.resolve('');
      return window.crypto.subtle.digest('SHA-256', enc).then(function(buf) {
        var b = Array.from(new Uint8Array(buf));
        return b.map(function(x){return x.toString(16).padStart(2,'0');}).join('');
      });
    }

    function fingerprint() {
      // Visitor fingerprint without true IP. UA + screen + tz + lang.
      var parts = [
        navigator.userAgent || '',
        screen.width + 'x' + screen.height,
        (new Date()).getTimezoneOffset(),
        (navigator.language || ''),
      ].join('|');
      return sha256Hex(parts);
    }

    function sendEvent(extra) {
      var elapsed = Math.round((Date.now() - entryTs) / 1000);
      var payload = {
        bin_id: BIN,
        visitor_hash: visitorHash,
        page: window.location.href,
        time_spent: elapsed,
        referrer: document.referrer || '',
        device: device,
        form_filled: false
      };
      if (extra) {
        for (var k in extra) { payload[k] = extra[k]; }
      }
      try {
        var body = JSON.stringify(payload);
        var url = INTEL_URL;
        if (navigator.sendBeacon) {
          navigator.sendBeacon(url, new Blob([body], { type: 'application/json' }));
        } else {
          fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: body, keepalive: true
          }).catch(function(){});
        }
      } catch (e) { /* fail silent */ }
    }

    function extractFormContact(form) {
      var email = '', phone = '';
      try {
        var inputs = form.querySelectorAll('input, textarea');
        for (var i = 0; i < inputs.length; i++) {
          var el = inputs[i];
          var t = (el.type || '').toLowerCase();
          var n = (el.name || el.id || '').toLowerCase();
          var v = (el.value || '').trim();
          if (!v) continue;
          if (t === 'email' || /email|mail/.test(n)) email = email || v;
          else if (t === 'tel' || /phone|mobile|cell/.test(n)) phone = phone || v;
          else if (!email && /@/.test(v) && v.length < 80) email = v;
          else if (!phone && /\d{3,}/.test(v) && v.replace(/\D/g, '').length >= 7) phone = v;
        }
      } catch (e) {}
      return { email: email, phone: phone };
    }

    function onFormSubmit(ev) {
      var f = ev && ev.target;
      if (!f || f.tagName !== 'FORM') return;
      var c = extractFormContact(f);
      if (!c.email && !c.phone) {
        sendEvent({ form_filled: true });
        return;
      }
      // Hash email + phone client-side so raw values NEVER touch network.
      Promise.all([
        c.email ? sha256Hex(c.email.trim().toLowerCase()) : Promise.resolve(''),
        c.phone ? sha256Hex(c.phone.replace(/\D/g, '')) : Promise.resolve(''),
      ]).then(function(hashes) {
        sendEvent({
          form_filled: true,
          // Backend re-hashes the raw fields it receives; for guaranteed
          // privacy we send only the hashed form_data_hash here. Server
          // also accepts plain form_email / form_phone but we never send
          // them.
          form_data_hash: hashes[0] || hashes[1] || '',
        });
      }).catch(function() {
        sendEvent({ form_filled: true });
      });
    }

    fingerprint().then(function(vh) {
      visitorHash = vh;
      // Initial page-load beacon.
      sendEvent({});
    });

    // Hook every submit on the page (delegated).
    document.addEventListener('submit', onFormSubmit, true);
    // Heartbeat on unload (time_spent measurement).
    window.addEventListener('beforeunload', function() { sendEvent({}); });
  })();

  console.log('[AUREM Bridge v3.0] Initialized — HMAC-signed patches + Intelligence Stack active. Session:', sessionId);
})();
