const CACHE = "frame-v1";
const IMG_CACHE = "frame-img-v1";

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;
  const url = new URL(request.url);

  // Masters' artwork/portrait images on Wikimedia Commons: cache-first. They are
  // public-domain and immutable, so once fetched they load instantly (and
  // offline) on every later view. Opaque (no-CORS) responses are cacheable too.
  if (url.hostname === "upload.wikimedia.org") {
    event.respondWith(
      caches.open(IMG_CACHE).then((cache) =>
        cache.match(request).then(
          (hit) =>
            hit ||
            fetch(request).then((res) => {
              if (res && (res.ok || res.type === "opaque")) cache.put(request, res.clone());
              return res;
            }),
        ),
      ),
    );
    return;
  }

  // Navigation requests: network-first, fall back to cache, then to "/".
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(request, copy));
          return res;
        })
        .catch(() =>
          caches
            .match(request)
            .then((r) => r || caches.match(new URL("./", self.location.href).pathname)),
        ),
    );
    return;
  }

  // Same-origin GET (assets + catalog JSON): stale-while-revalidate.
  if (url.origin === self.location.origin) {
    event.respondWith(
      caches.match(request).then((cached) => {
        const network = fetch(request)
          .then((res) => {
            const copy = res.clone();
            caches.open(CACHE).then((c) => c.put(request, copy));
            return res;
          })
          .catch(() => cached);
        return cached || network;
      }),
    );
  }
});
