// Right Ewaste ERP V5.0 – Progressive Web App Service Worker
const CACHE_NAME = 'right-ewaste-v5.0-cache-v2';
const PRECACHE_ASSETS = [
  '/',
  '/offline',
  '/static/css/shared.css',
  '/static/js/shared.js',
  '/static/images/logo.png',
  '/static/images/favicon.png',
  '/static/manifest.json',
  '/static/images/pwa/icon-192.png',
  '/static/images/pwa/icon-512.png'
];

// Install Event – Pre-cache static assets
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[ServiceWorker] Pre-caching ERP offline assets');
      return cache.addAll(PRECACHE_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

// Activate Event – Clean up legacy caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            console.log('[ServiceWorker] Removing obsolete cache:', cache);
            return caches.delete(cache);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch Event – Network-First for Navigation, Stale-While-Revalidate for Static Assets
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Skip non-GET requests or browser extension requests
  if (request.method !== 'GET' || !url.protocol.startsWith('http')) {
    return;
  }

  // HTML Navigation Requests (Network First with Offline Fallback)
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Cache fresh copy of successful navigation responses
          if (response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
          }
          return response;
        })
        .catch(() => {
          // Fallback to cache, or offline fallback page
          return caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            return caches.match('/offline');
          });
        })
    );
    return;
  }

  // Static Assets (Stale-While-Revalidate)
  if (
    url.pathname.startsWith('/static/') ||
    url.hostname.includes('cdn.jsdelivr.net') ||
    url.hostname.includes('fonts.googleapis.com') ||
    url.hostname.includes('fonts.gstatic.com')
  ) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        const fetchPromise = fetch(request).then((networkResponse) => {
          if (networkResponse.status === 200) {
            const responseClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, responseClone));
          }
          return networkResponse;
        }).catch(() => cachedResponse);

        return cachedResponse || fetchPromise;
      })
    );
    return;
  }

  // Default Network First for APIs / Data Endpoints
  event.respondWith(
    fetch(request).catch(() => caches.match(request))
  );
});

// Background Sync Shell for Offline Form Queueing
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-erp-queue') {
    console.log('[ServiceWorker] Background Syncing queued ERP offline transactions');
  }
});

// Push Notification Shell for System Alerts & Approvals
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : { title: 'Right Ewaste ERP', body: 'New System Notification' };
  const options = {
    body: data.body,
    icon: '/static/images/pwa/icon-192.png',
    badge: '/static/images/pwa/icon-192.png',
    vibrate: [100, 50, 100],
    data: { dateOfArrival: Date.now(), primaryKey: '1' }
  };
  event.waitUntil(self.registration.showNotification(data.title, options));
});
