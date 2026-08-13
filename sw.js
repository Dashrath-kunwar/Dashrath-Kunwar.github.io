/* Minimal offline support so the installed PWA isn't a blank page without a
   network. Bump CACHE when assets change — old caches are dropped on activate. */

const CACHE = 'dk-fc8d992d';

const PRECACHE = [
  './',
  'index.html',
  'about.html',
  'bookmarks.html',
  'projects.html',
  'writings.html',
  'install.html',
  '404.html',
  'style.css',
  'theme.js',
  'share.js',
  'img/preacher-in-pixelated-inferno.webp',
  'img/come-for-the-essays.webp',
  'img/banner-aqueduct.png',
  'img/about-placeholder.png',
  'img/thumos.png',
  'fonts/roboto-mono-latin.woff2',
  'fonts/unifraktur-latin.woff2',
  'favicon-96x96.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE)
      // Individual failures shouldn't abort the whole install.
      .then((cache) => Promise.allSettled(PRECACHE.map((url) => cache.add(url))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') return;
  if (new URL(request.url).origin !== self.location.origin) return;

  // Pages: network first, so edits show up immediately. Cache is the fallback.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((hit) => hit || caches.match('404.html')))
    );
    return;
  }

  // Static assets: cache first, they're immutable in practice.
  event.respondWith(
    caches.match(request).then(
      (hit) =>
        hit ||
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone();
            caches.open(CACHE).then((cache) => cache.put(request, copy));
          }
          return response;
        })
    )
  );
});
