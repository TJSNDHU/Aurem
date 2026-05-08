// La Vela Bianca Service Worker - Separate PWA from ReRoots
const CACHE_NAME = 'lavela-v1';
const LAVELA_ASSETS = [
  '/la-vela-bianca',
  '/lavela/oro-rosa',
  '/lavela/glow-club',
  '/lavela/lab',
  '/lavela/founder',
  '/lavela-icon-192.png',
  '/lavela-icon-512.png',
  '/lavela-manifest.json'
];

// Install - cache La Vela assets
self.addEventListener('install', (event) => {
  console.log('[La Vela SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[La Vela SW] Caching assets');
        return cache.addAll(LAVELA_ASSETS);
      })
      .catch((err) => console.log('[La Vela SW] Cache failed:', err))
  );
  self.skipWaiting();
});

// Activate - clean old caches
self.addEventListener('activate', (event) => {
  console.log('[La Vela SW] Activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== CACHE_NAME && cacheName.startsWith('lavela-')) {
            console.log('[La Vela SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch - network first, fallback to cache
self.addEventListener('fetch', (event) => {
  // Only handle La Vela routes
  const url = new URL(event.request.url);
  
  if (url.pathname.includes('lavela') || url.pathname.includes('la-vela-bianca')) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          // Clone and cache the response
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(event.request, responseClone);
          });
          return response;
        })
        .catch(() => {
          // Fallback to cache
          return caches.match(event.request);
        })
    );
  }
});

// Handle push notifications for La Vela
self.addEventListener('push', (event) => {
  const data = event.data?.json() || {};
  
  const options = {
    body: data.body || 'New update from La Vela Bianca!',
    icon: '/lavela-icon-192.png',
    badge: '/lavela-icon-192.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/la-vela-bianca'
    },
    actions: [
      { action: 'open', title: 'Open' },
      { action: 'close', title: 'Close' }
    ]
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'La Vela Bianca', options)
  );
});

// Handle notification click
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  if (event.action === 'open' || !event.action) {
    const url = event.notification.data?.url || '/la-vela-bianca';
    event.waitUntil(
      clients.openWindow(url)
    );
  }
});

console.log('[La Vela SW] Service Worker loaded');
