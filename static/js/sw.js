/* The phone app's service worker (spec 5, section 4). It receives push and
 * shows an offline page when the network fails. It stores NO rota, leave or
 * personal page: the only thing ever cached is /offline/, which is
 * self-contained. */
var CACHE = "shift-central-offline-v1";

self.addEventListener("install", function (event) {
  event.waitUntil(caches.open(CACHE).then(function (cache) { return cache.add("/offline/"); })
    .then(function () { return self.skipWaiting(); }));
});

self.addEventListener("activate", function (event) {
  event.waitUntil(caches.keys().then(function (keys) {
    return Promise.all(keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

// Pages come from the network. Only when it fails does the offline page show.
self.addEventListener("fetch", function (event) {
  if (event.request.mode !== "navigate") { return; }
  event.respondWith(fetch(event.request).catch(function () { return caches.match("/offline/"); }));
});

self.addEventListener("push", function (event) {
  var data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = {}; }
  var url = typeof data.url === "string" ? data.url : "/rota/";
  event.waitUntil(self.registration.showNotification(data.title || "AMG Shift Central", {
    body: data.body || "",
    tag: url,
    icon: "/static/img/icon-192.png",
    data: { url: url },
  }));
});

self.addEventListener("notificationclick", function (event) {
  event.notification.close();
  var target = new URL((event.notification.data && event.notification.data.url) || "/rota/", self.location.origin);
  // Only ever a page on this site, whatever the payload said.
  if (target.origin !== self.location.origin) { target = new URL("/rota/", self.location.origin); }
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then(function (windows) {
    for (var i = 0; i < windows.length; i++) {
      if ("focus" in windows[i]) { windows[i].navigate(target.href); return windows[i].focus(); }
    }
    return self.clients.openWindow(target.href);
  }));
});
