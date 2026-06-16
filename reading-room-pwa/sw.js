/* Minimal service worker — exists so Chrome/Edge will offer "Install".
   Network-first and deliberately NON-caching for PDFs and note data,
   so it can never serve you a stale book or a stale note. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', e => {
  // Pass everything straight through to the network. No offline cache.
  e.respondWith(fetch(e.request));
});
