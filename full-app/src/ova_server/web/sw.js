// The app shell works offline; everything the agent says needs the network.
const SHELL = "ova-shell-v1";
const FILES = ["/", "/static/app.css", "/static/app.js", "/static/voice.js",
               "/static/icon.svg", "/static/icon-192.png", "/manifest.webmanifest"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(FILES)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.pathname.startsWith("/api/") ||
      url.pathname.startsWith("/ws/") || url.origin !== location.origin) return;
  e.respondWith(fetch(e.request).then((r) => {
    if (FILES.includes(url.pathname)) caches.open(SHELL).then((c) => c.put(e.request, r.clone()));
    return r;
  }).catch(() => caches.match(e.request)));
});
