/**
 * AUREM Service Worker — v3 (Chunk-safe PWA)
 * ===========================================
 * CRITICAL FIX (Feb 2026): Resolve ChunkLoadError "Unexpected token '<'"
 *   caused by stale HTML cache referencing dead Webpack chunks.
 *
 * Strategies:
 * - HTML/navigation: network-only (never cache app shell HTML — always fresh index.html
 *   so Webpack chunk refs stay in sync with what the server has on disk).
 * - Static hashed assets (/static/*): network-first with runtime cache (safe because
 *   file hashes change per build; never serve a bad 404/HTML as JS).
 * - API: network-first, cache fallback for offline metrics.
 * - JS/CSS that returns HTML (server fallback) is DROPPED so Webpack triggers its own
 *   retry via the window.chunkLoadErrorHandler in index.js.
 */

const SW_VERSION = 'aurem-sw-v4-20260430';
const RUNTIME_CACHE = `aurem-runtime-${SW_VERSION}`;
const API_CACHE = `aurem-api-${SW_VERSION}`;

// Install: activate immediately, no preloaded shell (we always hit network for HTML)
self.addEventListener('install', (event) => {
  self.skipWaiting();
});

// Activate: nuke ALL previous caches (including v1, v2, ora-ai-*) and claim clients
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k !== RUNTIME_CACHE && k !== API_CACHE)
          .map((k) => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

function isStaticAsset(pathname) {
  return /\.(js|css|png|jpg|jpeg|svg|ico|woff2?|ttf|eot|webp|map)(\?|$)/.test(pathname)
    || pathname.startsWith('/static/');
}

function isNavigation(request, url) {
  return request.mode === 'navigate'
    || (request.method === 'GET' && (request.headers.get('accept') || '').includes('text/html'));
}

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Only handle same-origin requests
  if (url.origin !== self.location.origin) return;

  // 1) API calls → network-first, cache fallback
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstApi(request));
    return;
  }

  // 2) Navigation / HTML → network ONLY (no cache, avoids stale chunk refs)
  if (isNavigation(request, url)) {
    event.respondWith(networkOnlyHtml(request));
    return;
  }

  // 3) Static hashed assets → network-first, cache hit only if network fails
  if (isStaticAsset(url.pathname)) {
    event.respondWith(networkFirstAsset(request));
    return;
  }

  // 4) Default: pass-through to network
  event.respondWith(fetch(request).catch(() => new Response('', { status: 504 })));
});

async function networkOnlyHtml(request) {
  try {
    const response = await fetch(request, { cache: 'no-store' });
    return response;
  } catch {
    // Truly offline → show offline page
    return new Response(offlinePage(), {
      headers: { 'Content-Type': 'text/html' },
      status: 200,
    });
  }
}

async function networkFirstAsset(request) {
  try {
    const response = await fetch(request);
    // CRITICAL: If server returns HTML for a JS/CSS asset (SPA catch-all), DO NOT cache it
    // and return a 404 so Webpack's chunkLoadError handler triggers a hard reload.
    const contentType = response.headers.get('content-type') || '';
    const url = new URL(request.url);
    const isJs = /\.js($|\?)/.test(url.pathname);
    const isCss = /\.css($|\?)/.test(url.pathname);
    if (response.ok && ((isJs && !contentType.includes('javascript')) ||
                        (isCss && !contentType.includes('css')))) {
      return new Response('', { status: 404 });
    }
    if (response.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, response.clone()).catch(() => {});
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response('', { status: 503 });
  }
}

async function networkFirstApi(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      cache.put(request, response.clone()).catch(() => {});
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response(JSON.stringify({ error: 'offline', cached: false }), {
      headers: { 'Content-Type': 'application/json' },
      status: 503,
    });
  }
}

function offlinePage() {
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ORA — Offline</title>
<style>*{margin:0;box-sizing:border-box}body{background:#0A0A0F;color:#E8E4D9;font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;padding:20px}
.c{text-align:center;max-width:400px}.logo{width:60px;height:60px;border-radius:16px;background:linear-gradient(135deg,#D4B977,#B19A5E);display:flex;align-items:center;justify-content:center;margin:0 auto 24px;font-weight:900;font-size:24px;color:#0A0A00}
h1{font-size:20px;margin-bottom:8px}p{color:#8A8473;font-size:13px;line-height:1.6;margin-bottom:20px}
.retry{background:rgba(212,175,55,0.1);color:#D4AF37;border:1px solid rgba(212,175,55,0.2);padding:10px 24px;border-radius:12px;font-weight:700;font-size:12px;cursor:pointer;margin-top:12px}
</style></head><body><div class="c"><div class="logo">A</div><h1>ORA is Offline</h1><p>Your connection is down. Please retry when online.</p>
<button class="retry" onclick="location.reload()">Retry Connection</button></div></body></html>`;
}

// ═══════════════════════════════════════════════════
// MESSAGE HANDLER (for client-triggered SW updates)
// ═══════════════════════════════════════════════════
self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING' || event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  if (event.data === 'CLEAR_CACHES' || event.data?.type === 'CLEAR_CACHES') {
    event.waitUntil(
      caches.keys().then((keys) => Promise.all(keys.map((k) => caches.delete(k))))
    );
  }
});

// ═══════════════════════════════════════════════════
// PUSH NOTIFICATION HANDLER
// ═══════════════════════════════════════════════════

self.addEventListener('push', event => {
  let data = { title: 'AUREM Notification', body: '', icon: '/ora-icon.png', url: '/dashboard' };
  try {
    data = { ...data, ...event.data.json() };
  } catch {}

  const options = {
    body: data.body,
    icon: data.icon || '/ora-icon.png',
    badge: data.badge || '/ora-badge.png',
    tag: data.tag || 'aurem',
    vibrate: [200, 100, 200],
    data: { url: data.url || '/dashboard', actions: data.actions || [] },
    requireInteraction: !!data.require_interaction,
  };

  if (data.actions && data.actions.length) {
    options.actions = data.actions.map(a => ({
      action: a.action,
      title: a.title,
    }));
  }

  event.waitUntil(self.registration.showNotification(data.title, options));
});

self.addEventListener('notificationclick', event => {
  event.notification.close();

  const action = event.action;
  const data = event.notification.data || {};

  if (action && data.actions) {
    const actionConfig = data.actions.find(a => a.action === action);
    if (actionConfig && actionConfig.url) {
      event.waitUntil(
        fetch(actionConfig.url, { method: 'POST' })
          .then(() => {
            return self.registration.showNotification('Action Completed', {
              body: actionConfig.confirm || 'Done',
              icon: '/ora-icon.png',
              tag: 'action-confirm',
            });
          })
          .catch(() => {})
      );
      return;
    }
  }

  event.waitUntil(
    self.clients.matchAll({ type: 'window' }).then(clients => {
      const targetUrl = data.url || '/dashboard';
      for (const client of clients) {
        if (client.url.includes(targetUrl) && 'focus' in client) {
          return client.focus();
        }
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
