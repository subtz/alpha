const CACHE_NAME = 'sqms-pwa-v2';
const PRECACHE_RESOURCES = [
  '/static/calc/styles.css',
  '/static/calc/images/logo.png',
  '/static/calc/images/whatsapp.png',
  '/static/calc/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_RESOURCES))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(name => {
          if (name !== CACHE_NAME) {
            return caches.delete(name);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  // Never cache profile pictures or media files
  if (event.request.url.includes('/media/')) {
    event.respondWith(fetch(event.request));
    return;
  }

  if (event.request.method !== 'GET') {
    return;
  }

  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      return cachedResponse || fetch(event.request);
    })
  );
});

self.addEventListener('push', event => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: "SQMS Notification", body: event.data.text() };
    }
  }

  const title = data.title || "SQMS Notification";
  const options = {
    body: data.body || "You have a new update.",
    icon: "/static/calc/images/default-avatar.svg",
    badge: "/static/calc/images/logo.png"
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(windowClients => {
      for (let i = 0; i < windowClients.length; i++) {
        let client = windowClients[i];
        if (client.url === '/' && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow('/notifications/');
      }
    })
  );
});
