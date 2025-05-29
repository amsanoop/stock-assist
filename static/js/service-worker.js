const CACHE_NAME = "stockassist-cache-v1";
const urlsToCache = [
  "/",
  "/stocks",
  "/chat",
  "/pricing",
  "/news",
  "/offline",
  "/js/base.js",
  "/js/main.js",
  "/js/index.js",
  "/js/news.js",
  "/js/pwa.js",
  "/js/pwa-announcement.js",
  "/css/output.css",
  "/css/chat.css",
  "/css/stocks.css",
  "/css/pricing.css",
  "/css/pwa.css",
  "/images/StockAssist-min.jpg",
  "/icons/favicon.ico",
  "/icons/apple-touch-icon.png",
];

const OFFLINE_URL = "/offline";

self.addEventListener("install", (event) => {
  /**
   * Installs the service worker and caches the defined URLs.
   * @param {ExtendableEvent} event - The install event.
   */
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(urlsToCache);
    })
  );
});

self.addEventListener("fetch", (event) => {
  /**
   * Intercepts fetch requests and serves cached content or fetches from the network.
   * @param {FetchEvent} event - The fetch event.
   */
  if (
    event.request.mode === "navigate" ||
    (event.request.method === "GET" &&
      event.request.headers.get("accept").includes("text/html"))
  ) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(OFFLINE_URL);
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((response) => {
      if (response) {
        return response;
      }
      return fetch(event.request)
        .then((response) => {
          if (!response || response.status !== 200 || response.type !== "basic") {
            return response;
          }

          const responseToCache = response.clone();

          caches.open(CACHE_NAME).then((cache) => {
            if (event.request.url.indexOf("/api/") === -1) {
              cache.put(event.request, responseToCache);
            }
          });

          return response;
        })
        .catch(() => {
          if (event.request.destination === "image") {
            return new Response();
          }
        });
    })
  );
});

self.addEventListener("activate", (event) => {
  /**
   * Activates the service worker and removes old caches.
   * @param {ExtendableEvent} event - The activate event.
   */
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

self.addEventListener("message", (event) => {
  /**
   * Handles messages sent to the service worker.
   * @param {ExtendableMessageEvent} event - The message event.
   */
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});