// Test-bench service worker: always serve the freshest /test HTML so the page
// reflects the latest deploy without ?v cache-busting. Network-first for the
// document, bypassing the HTTP cache (GitHub Pages stamps every page with
// Cache-Control: max-age=600, which we can't change). Scope is /test/ because
// this file is served from there. Falls back to a normal fetch when offline.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => {
  const req = e.request;
  const isDoc = req.mode === 'navigate' ||
    (req.method === 'GET' && req.destination === 'document');
  if (!isDoc) return;
  e.respondWith(
    fetch(req.url, { cache: 'no-store' }).catch(() => fetch(req))
  );
});
