const CACHE_NAME = 'pagevault-v3';
const COVER_CACHE = 'pagevault-covers-v1';
const CORE_ASSETS = [
  '/', '/stats',
  '/static/manifest.webmanifest', '/static/icon.svg',
  '/static/vendor/fonts/fonts.css',
];
// Cross-origin hosts that serve book cover images.
const COVER_HOSTS = ['covers.openlibrary.org', 'books.google.com', 'books.googleusercontent.com'];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(CORE_ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      const keep = [CACHE_NAME, COVER_CACHE];
      return Promise.all(keys.filter(key => !keep.includes(key)).map(key => caches.delete(key)));
    }).then(() => self.clients.claim())
  );
});

function cachePut(request, response) {
  if (response && response.status === 200) {
    const cloned = response.clone();
    caches.open(CACHE_NAME).then(cache => cache.put(request, cloned));
  }
  return response;
}

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;

  // Book covers are cross-origin images. Cache them (cache-first) so a library
  // you have already browsed still shows its covers when offline. Opaque
  // (no-cors) responses cannot be inspected but render correctly in <img>.
  if (COVER_HOSTS.includes(url.hostname)) {
    event.respondWith(
      caches.open(COVER_CACHE).then(cache =>
        cache.match(request).then(cached => cached || fetch(request).then(response => {
          if (response && (response.ok || response.type === 'opaque')) {
            cache.put(request, response.clone());
          }
          return response;
        }).catch(() => cached))
      )
    );
    return;
  }

  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  // Pages (navigations): network-first so a new app version is picked up
  // immediately; the cached copy is only an offline fallback.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => cachePut(request, response))
        .catch(() => caches.match(request).then(cached => cached || caches.match('/')))
    );
    return;
  }

  // Static assets: stale-while-revalidate — serve from cache instantly and
  // refresh the cached copy in the background.
  event.respondWith(
    caches.match(request).then(cached => {
      const refresh = fetch(request)
        .then(response => cachePut(request, response))
        .catch(() => cached);
      return cached || refresh;
    })
  );
});
