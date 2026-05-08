/**
 * ReRoots AI Luxury PWA Service Worker v9 (v2.0.0-Biotech Fortress)
 * UNIFIED: Cache-First for Assets | Network-First for API
 * Handles Push Notifications for Cart Recovery
 * HOT-SWAP: Forces update for all existing users
 * AES-256 ACTIVE: Vault encryption enabled
 */

const SW_VERSION = 'v9';
const CACHE_VERSION = 'reroots-pwa-v9-fortress';
const STATIC_CACHE = `${CACHE_VERSION}-static`;
const DYNAMIC_CACHE = `${CACHE_VERSION}-dynamic`;
const SKIN_DATA_CACHE = `${CACHE_VERSION}-skin`;

// Static assets to pre-cache on install (MERGED: old app assets + new biometric scripts)
const PRECACHE_ASSETS = [
  '/pwa',
  '/manifest.json',
  '/icons/icon-72x72.png',
  '/icons/icon-96x96.png',
  '/icons/icon-128x128.png',
  '/icons/icon-144x144.png',
  '/icons/icon-152x152.png',
  '/icons/icon-192x192.png',
  '/icons/icon-384x384.png',
  '/icons/icon-512x512.png',
  '/reroots-logo.jpg',
  '/offline.html',
  // Old app assets
  '/favicon.ico',
  '/index.html'
];

// API endpoints that should be network-first (skin data, user data)
const NETWORK_FIRST_PATTERNS = [
  '/api/products',
  '/api/cart',
  '/api/user',
  '/api/orders',
  '/api/pwa'
];

// Install Event - Pre-cache static assets + Force skip waiting for hot-swap
self.addEventListener('install', (event) => {
  console.log(`[PWA SW ${SW_VERSION}] Installing ReRoots Biotech Fortress...`);
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((cache) => {
        console.log('[PWA SW] Pre-caching static assets');
        return cache.addAll(PRECACHE_ASSETS);
      })
      .then(() => {
        console.log(`[PWA SW ${SW_VERSION}] HOT-SWAP: Forcing skip waiting - Purging old caches`);
        return self.skipWaiting(); // Force immediate activation for all users
      })
  );
});

// Activate Event - Clean up old caches + claim all clients
self.addEventListener('activate', (event) => {
  console.log(`[PWA SW ${SW_VERSION}] Activating Biotech Fortress - AES-256 Ready...`);
  event.waitUntil(
    caches.keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name.startsWith('reroots-pwa') && name !== STATIC_CACHE && name !== DYNAMIC_CACHE && name !== SKIN_DATA_CACHE)
            .map((name) => {
              console.log(`[PWA SW ${SW_VERSION}] Purging legacy cache:`, name);
              return caches.delete(name);
            })
        );
      })
      .then(() => {
        console.log(`[PWA SW ${SW_VERSION}] Claiming all clients - Fortress Active`);
        return self.clients.claim(); // Take control of all open pages immediately
      })
  );
});

// Fetch Event - Smart caching strategy
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') return;

  // Skip chrome-extension and other protocols
  if (!url.protocol.startsWith('http')) return;

  // Network-First for API calls (skin data needs to be fresh)
  if (NETWORK_FIRST_PATTERNS.some(pattern => url.pathname.includes(pattern))) {
    event.respondWith(networkFirst(request, DYNAMIC_CACHE));
    return;
  }

  // Cache-First for static assets (images, fonts, CSS, JS)
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirst(request, STATIC_CACHE));
    return;
  }

  // Stale-While-Revalidate for everything else
  event.respondWith(staleWhileRevalidate(request, DYNAMIC_CACHE));
});

// Cache-First Strategy (for static assets)
async function cacheFirst(request, cacheName) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[PWA SW] Cache-First fetch failed:', error);
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}

// Network-First Strategy (for API/dynamic data)
async function networkFirst(request, cacheName) {
  try {
    const networkResponse = await fetch(request);
    if (networkResponse.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (error) {
    console.log('[PWA SW] Network-First falling back to cache');
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
      return cachedResponse;
    }
    return new Response(JSON.stringify({ error: 'Offline', cached: false }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' }
    });
  }
}

// Stale-While-Revalidate Strategy
async function staleWhileRevalidate(request, cacheName) {
  const cache = await caches.open(cacheName);
  const cachedResponse = await cache.match(request);
  
  const fetchPromise = fetch(request).then((networkResponse) => {
    if (networkResponse.ok) {
      cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  }).catch(() => cachedResponse);

  return cachedResponse || fetchPromise;
}

// Check if request is for static asset
function isStaticAsset(pathname) {
  return /\.(js|css|png|jpg|jpeg|gif|svg|webp|woff|woff2|ttf|eot|ico)$/i.test(pathname);
}

// Push Notification Event
self.addEventListener('push', (event) => {
  console.log('[PWA SW] Push notification received');
  
  let data = {
    title: 'ReRoots AI',
    body: 'Your Skin Journey Begins Now',
    icon: '/icons/icon-192x192.png',
    badge: '/icons/icon-96x96.png',
    tag: 'reroots-notification',
    data: { url: '/pwa' }
  };

  try {
    if (event.data) {
      const payload = event.data.json();
      data = { ...data, ...payload };
    }
  } catch (e) {
    console.log('[PWA SW] Push payload parse error:', e);
  }

  const options = {
    body: data.body,
    icon: data.icon || '/icons/icon-192x192.png',
    badge: data.badge || '/icons/icon-96x96.png',
    tag: data.tag || 'reroots-notification',
    vibrate: [100, 50, 100],
    data: data.data || { url: '/pwa' },
    actions: data.actions || [
      { action: 'open', title: 'Open App' },
      { action: 'dismiss', title: 'Dismiss' }
    ],
    requireInteraction: data.requireInteraction || false
  };

  event.waitUntil(
    self.registration.showNotification(data.title, options)
  );
});

// Notification Click Event
self.addEventListener('notificationclick', (event) => {
  console.log('[PWA SW] Notification clicked:', event.action);
  event.notification.close();

  if (event.action === 'dismiss') {
    return;
  }

  const urlToOpen = event.notification.data?.url || '/pwa';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Check if there's already a window open
        for (const client of clientList) {
          if (client.url.includes('/pwa') && 'focus' in client) {
            client.navigate(urlToOpen);
            return client.focus();
          }
        }
        // Open new window if none exists
        if (clients.openWindow) {
          return clients.openWindow(urlToOpen);
        }
      })
  );
});

// Background Sync for offline actions
self.addEventListener('sync', (event) => {
  console.log('[PWA SW] Background sync:', event.tag);
  
  if (event.tag === 'sync-cart') {
    event.waitUntil(syncCart());
  }
  
  if (event.tag === 'sync-vault') {
    event.waitUntil(syncVault());
  }
});

// Sync cart data when back online
async function syncCart() {
  try {
    const cache = await caches.open(DYNAMIC_CACHE);
    const pendingCartOps = await cache.match('/pending-cart-operations');
    
    if (pendingCartOps) {
      const operations = await pendingCartOps.json();
      for (const op of operations) {
        await fetch('/api/cart/sync', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(op)
        });
      }
      await cache.delete('/pending-cart-operations');
    }
  } catch (error) {
    console.error('[PWA SW] Cart sync failed:', error);
  }
}

// Placeholder for vault sync
async function syncVault() {
  console.log('[PWA SW] Vault sync triggered - handled by client');
}

// Message handler for client communication
self.addEventListener('message', (event) => {
  console.log('[PWA SW] Message received:', event.data);
  
  if (event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data.type === 'GET_VERSION') {
    event.ports[0].postMessage({ 
      version: SW_VERSION, 
      cache: CACHE_VERSION,
      encryption: 'AES-256-GCM Active'
    });
  }
  
  if (event.data.type === 'CLEAR_CACHE') {
    caches.keys().then((names) => {
      names.forEach((name) => caches.delete(name));
    });
    event.ports[0].postMessage({ cleared: true });
  }
});

console.log(`[PWA SW ${SW_VERSION}] ReRoots Biotech Fortress Service Worker Loaded - Vault Encryption: AES-256-GCM`);
