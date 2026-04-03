// ReRoots PWA Service Worker - v9 Complete Offline Support
// Implements:
// - Cache-first for static assets
// - Network-first with cache fallback for API
// - Offline mode with cached products
// - Background sync for cart operations
/* eslint-disable no-restricted-globals */
'use strict';

const CACHE_VERSION = 'v9';
const STATIC_CACHE = `reroots-static-${CACHE_VERSION}`;
const DYNAMIC_CACHE = `reroots-dynamic-${CACHE_VERSION}`;
const FONT_CACHE = `reroots-fonts-${CACHE_VERSION}`;
const IMAGE_CACHE = `reroots-images-${CACHE_VERSION}`;
const API_CACHE = `reroots-api-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline.html';

// ============================================================
// STATIC ASSETS - Always cache on install
// ============================================================
const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  '/logo.png',
  '/reroots-logo.jpg',
  '/favicon.svg'
];

// ============================================================
// API ROUTES TO CACHE - Serve from cache when offline
// ============================================================
const CACHED_APIS = [
  '/api/products',
  '/api/chat-widget/config',
  '/api/collections'
];

// Cache duration (in seconds)
const CACHE_DURATION = {
  fonts: 30 * 24 * 60 * 60,    // 30 days
  images: 7 * 24 * 60 * 60,     // 7 days
  assets: 24 * 60 * 60,         // 1 day
  api: 60 * 60                   // 1 hour (for product data)
};

// URLs that should NEVER be cached
const NO_CACHE_URLS = [
  '/manifest.json',
  '/manifest.webmanifest',
  '/.well-known/',
  '/api/auth/',
  '/api/checkout/',
  '/api/orders/',
  '/api/ai/'
];

// Font patterns
const FONT_PATTERNS = [
  /\.woff2?$/i,
  /\.ttf$/i,
  /fontsource/i,
  /\/static\/media\/.*\.(woff2?|ttf)$/i
];

// Image patterns
const IMAGE_PATTERNS = [
  /\.(jpg|jpeg|png|gif|webp|avif|svg)$/i,
  /res\.cloudinary\.com/i,
  /customer-assets\.emergentagent\.com/i,
  /images\.unsplash\.com/i
];

// ============================================================
// HELPER FUNCTIONS
// ============================================================

const matchesPattern = (url, patterns) => {
  const urlString = url.toString();
  return patterns.some(pattern => 
    pattern instanceof RegExp ? pattern.test(urlString) : urlString.includes(pattern)
  );
};

const shouldNotCache = (url) => {
  const urlString = url.toString();
  return NO_CACHE_URLS.some(pattern => urlString.includes(pattern));
};

// Network first, then cache fallback
const networkFirstThenCache = async (request, cacheName) => {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.ok) {
      // Clone and cache the fresh response
      const cache = await caches.open(cacheName);
      await cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    // Network failed, try cache
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      console.log('[SW] Serving from cache (offline):', request.url);
      return cachedResponse;
    }
    throw error;
  }
};

// Cache first, then network
const cacheFirstThenNetwork = async (request, cacheName) => {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    // Refresh cache in background
    fetch(request).then(async (networkResponse) => {
      if (networkResponse && networkResponse.ok) {
        const cache = await caches.open(cacheName);
        await cache.put(request, networkResponse);
      }
    }).catch(() => {});
    return cachedResponse;
  }
  
  const networkResponse = await fetch(request);
  if (networkResponse && networkResponse.ok) {
    const cache = await caches.open(cacheName);
    await cache.put(request, networkResponse.clone());
  }
  return networkResponse;
};

// ============================================================
// INSTALL EVENT - Cache static assets
// ============================================================
self.addEventListener('install', (event) => {
  console.log('[SW] Installing service worker v9...');
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      console.log('[SW] Caching static assets');
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// ============================================================
// ACTIVATE EVENT - Clean old caches
// ============================================================
self.addEventListener('activate', (event) => {
  console.log('[SW] Activating service worker v9...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => {
            return name.startsWith('reroots-') && !name.endsWith(CACHE_VERSION);
          })
          .map((name) => {
            console.log('[SW] Deleting old cache:', name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// ============================================================
// FETCH EVENT - Smart caching strategies
// ============================================================
self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  
  const url = new URL(event.request.url);
  
  // Skip URLs that should never be cached
  if (shouldNotCache(url)) {
    return;
  }
  
  // ============================================================
  // API REQUESTS - Network first with cache fallback
  // ============================================================
  if (url.pathname.startsWith('/api')) {
    // Check if this API should be cached for offline
    const shouldCacheApi = CACHED_APIS.some(api => url.pathname.startsWith(api));
    
    if (shouldCacheApi) {
      event.respondWith(
        networkFirstThenCache(event.request, API_CACHE)
          .catch(() => {
            // Complete network failure - return cached or error
            return caches.match(event.request).then(cached => {
              if (cached) return cached;
              return new Response(
                JSON.stringify({ error: 'You are offline', offline: true }),
                { 
                  status: 503, 
                  headers: { 'Content-Type': 'application/json' } 
                }
              );
            });
          })
      );
      return;
    }
    
    // Non-cached API - pass through
    return;
  }
  
  // ============================================================
  // NAVIGATION REQUESTS - Network first with offline fallback
  // ============================================================
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request)
        .catch(() => {
          return caches.match(OFFLINE_URL);
        })
    );
    return;
  }
  
  // ============================================================
  // SKIP Analytics and tracking
  // ============================================================
  if (url.hostname.includes('google-analytics') || 
      url.hostname.includes('googletagmanager') ||
      url.hostname.includes('facebook') ||
      url.hostname.includes('posthog')) {
    return;
  }
  
  // ============================================================
  // FONTS - Cache first (they rarely change)
  // ============================================================
  if (matchesPattern(url, FONT_PATTERNS)) {
    event.respondWith(cacheFirstThenNetwork(event.request, FONT_CACHE));
    return;
  }
  
  // ============================================================
  // IMAGES - Cache first (aggressive caching)
  // ============================================================
  if (matchesPattern(url, IMAGE_PATTERNS)) {
    event.respondWith(cacheFirstThenNetwork(event.request, IMAGE_CACHE));
    return;
  }
  
  // ============================================================
  // JS/CSS ASSETS - Stale while revalidate
  // ============================================================
  if (/\.(js|css)$/i.test(url.pathname)) {
    event.respondWith(cacheFirstThenNetwork(event.request, DYNAMIC_CACHE));
    return;
  }
  
  // ============================================================
  // DEFAULT - Network first
  // ============================================================
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// ============================================================
// MESSAGE HANDLER - Cache control commands
// ============================================================
self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data?.type === 'CLEAR_CACHE') {
    caches.keys().then((names) => {
      names.forEach((name) => caches.delete(name));
    });
  }
  
  // Prefetch product pages for instant navigation
  if (event.data?.type === 'PREFETCH_PRODUCT') {
    const { slug } = event.data;
    if (slug) {
      fetch(`/api/products/${slug}`)
        .then(response => {
          if (response.ok) {
            caches.open(API_CACHE).then(cache => {
              cache.put(`/api/products/${slug}`, response);
            });
          }
        })
        .catch(() => {});
    }
  }
  
  // Prefetch all products for offline browsing
  if (event.data?.type === 'PREFETCH_ALL_PRODUCTS') {
    fetch('/api/products')
      .then(response => {
        if (response.ok) {
          caches.open(API_CACHE).then(cache => {
            cache.put('/api/products', response);
          });
        }
      })
      .catch(() => {});
  }
});

// ============================================================
// BACKGROUND SYNC - Sync cart operations when back online
// ============================================================
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-cart') {
    event.waitUntil(syncCart());
  }
});

async function syncCart() {
  const cache = await caches.open(DYNAMIC_CACHE);
  const pendingOps = await cache.match('pending-cart-ops');
  
  if (pendingOps) {
    try {
      const ops = await pendingOps.json();
      for (const op of ops) {
        try {
          await fetch(op.url, {
            method: op.method,
            headers: op.headers,
            body: op.body
          });
          console.log('[SW] Synced cart operation:', op.url);
        } catch (e) {
          console.log('[SW] Failed to sync cart op:', e);
        }
      }
      await cache.delete('pending-cart-ops');
    } catch (e) {
      console.log('[SW] Failed to parse pending ops:', e);
    }
  }
}

// ============================================================
// PERIODIC SYNC - Keep cached data fresh
// ============================================================
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'refresh-products') {
    event.waitUntil(refreshProducts());
  }
});

async function refreshProducts() {
  try {
    const response = await fetch('/api/products');
    if (response.ok) {
      const cache = await caches.open(API_CACHE);
      await cache.put('/api/products', response);
      console.log('[SW] Products cache refreshed');
    }
  } catch (e) {
    console.log('[SW] Failed to refresh products:', e);
  }
}

console.log('[SW] Service worker v9 loaded');
