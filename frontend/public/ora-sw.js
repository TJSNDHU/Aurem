const CACHE_NAME = 'ora-ai-v5';
const SHELL_ASSETS = [
  '/ora',
  '/manifest.json',
  '/favicon.svg',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  // Never intercept API calls
  if (url.pathname.startsWith('/api')) return;
  // Only handle /ora routes
  if (!url.pathname.startsWith('/ora')) return;
  event.respondWith(
    fetch(event.request).catch(() =>
      caches.match(event.request).then((cached) => cached || caches.match('/ora'))
    )
  );
});

/* ─── Push Notification Handler with Haptics ─── */
const HAPTIC_PATTERNS = {
  vip_lead:     [200, 100, 200],
  payment:      [100, 50, 100, 50, 200],
  invoice_paid: [100, 50, 100, 50, 200],
  approval:     [300, 100, 300, 100, 300],
  approval_needed: [300, 100, 300, 100, 300],
  brief:        [100],
  morning_brief:[100],
  alert:        [500, 100, 500],
  anomaly_detected: [500, 100, 500],
  pipeline:     [150, 75, 150],
  pipeline_completed: [150, 75, 150],
  site_fixed:   [100, 50, 100],
  website_issue:[100, 50, 100],
  welcome:      [100],
};

self.addEventListener('push', (event) => {
  if (!event.data) return;
  try {
    const data = event.data.json();
    const options = {
      body: data.body || '',
      icon: data.icon || '/ora-icon.png',
      badge: data.badge || '/ora-badge.png',
      tag: data.tag || 'ora',
      data: { url: data.url || '/ora', ...data.data },
      requireInteraction: !!data.actions?.length,
    };
    if (data.actions?.length) {
      options.actions = data.actions;
    }
    // Haptic vibration (Android only, silently ignored on iOS)
    const vibrate = data.vibrate || HAPTIC_PATTERNS[data.tag?.replace('ora-', '')] || [200];
    options.vibrate = vibrate;

    event.waitUntil(self.registration.showNotification(data.title || 'ORA', options));
  } catch (e) {
    console.warn('[ORA-SW] Push parse error:', e);
  }
});

/* ─── Notification Click + Action Handler ─── */
self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const action = event.action;
  const data = event.notification.data || {};
  const url = data.url || '/ora';

  // If an action button was clicked, send to backend
  if (action) {
    event.waitUntil(
      fetch('/api/ora/notifications/action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: action,
          tenant_id: data.tenant_id || '',
          notification_id: data.notification_id || '',
        }),
      }).catch(() => {}).then(() => {
        return self.clients.matchAll({ type: 'window' }).then((clients) => {
          const existing = clients.find(c => c.url.includes('/ora'));
          if (existing) { existing.focus(); return; }
          return self.clients.openWindow(url);
        });
      })
    );
  } else {
    event.waitUntil(
      self.clients.matchAll({ type: 'window' }).then((clients) => {
        const existing = clients.find(c => c.url.includes('/ora'));
        if (existing) { existing.focus(); return; }
        return self.clients.openWindow(url);
      })
    );
  }
});
