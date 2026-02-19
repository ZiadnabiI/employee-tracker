const CACHE_NAME = 'inframe-monitor-v1';
const ASSETS_TO_CACHE = [
    '/', // Dashboard
    '/static/LOGO.png',
    'https://cdn.tailwindcss.com',
    'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
    'https://cdn.jsdelivr.net/npm/chart.js',
    'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap'
];

// Install Event - Cache Core Assets
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME).then((cache) => {
            console.log('[Service Worker] Caching App Shell');
            return cache.addAll(ASSETS_TO_CACHE);
        }).then(() => self.skipWaiting())
    );
});

// Activate Event - Clean Up Old Caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[Service Worker] Clearing Old Cache', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch Event - Network First Strategy for APIs, Stale-While-Revalidate for Assets
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // API Calls: Always go to Network First, fallback to cache if offline
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(
            fetch(event.request).catch(async () => {
                const cache = await caches.open(CACHE_NAME);
                const cachedResponse = await cache.match(event.request);
                return cachedResponse;
            })
        );
        return;
    }

    // Static Assets / HTML: Go to Cache First, then Network
    event.respondWith(
        caches.match(event.request).then((cachedResponse) => {
            if (cachedResponse) {
                // We found it in the cache!
                return cachedResponse;
            }

            // Not in cache, fetch from network
            return fetch(event.request).then((networkResponse) => {
                // Cache the newly fetched resource for future requests
                if (event.request.method === 'GET') {
                    const responseToCache = networkResponse.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseToCache);
                    });
                }
                return networkResponse;
            }).catch(() => {
                // Offline Fallback Page (Optional)
                /* if (event.request.headers.get('accept').includes('text/html')) {
                    return caches.match('/offline.html');
                } */
            });
        })
    );
});

// Push Notification Event (Future Proofing)
self.addEventListener('push', (event) => {
    let rawData = event.data ? event.data.text() : '{"title": "Alert", "body": "Employee Status Changed"}';
    try {
        const data = JSON.parse(rawData);
        const options = {
            body: data.body,
            icon: '/static/LOGO.png',
            badge: '/static/LOGO.png',
            vibrate: [200, 100, 200]
        };
        event.waitUntil(self.registration.showNotification(data.title, options));
    } catch (e) {
        console.error("Push Error", e);
    }
});
