// A service worker whose only job is to serve this folder with the two headers that make a
// page "cross-origin isolated". Browsers only allow SharedArrayBuffer (which the page uses so
// a running program can wait for the keyboard, and so Stop can interrupt Python) on isolated
// pages, and GitHub Pages cannot set headers itself.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()));

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.cache === 'only-if-cached' && request.mode !== 'same-origin') return;
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.status === 0) return response; // opaque: cannot be changed
        const headers = new Headers(response.headers);
        headers.set('Cross-Origin-Embedder-Policy', 'require-corp');
        headers.set('Cross-Origin-Opener-Policy', 'same-origin');
        if (!headers.has('Cross-Origin-Resource-Policy')) {
          headers.set('Cross-Origin-Resource-Policy', 'cross-origin');
        }
        return new Response(response.body, {
          status: response.status, statusText: response.statusText, headers,
        });
      })
      .catch(() => Response.error()),
  );
});
