/* Fantasy Hockey service worker: push alerts, plus a fallback copy of the page.
   Network first: when online you always get the newest build. The saved copy is only used with no signal. */
var CACHE = 'fh-page-v1';
self.addEventListener('fetch', function (e) {
  var r = e.request;
  if (r.method !== 'GET' || new URL(r.url).origin !== self.location.origin) return;
  var key = r.url.split('?')[0].split('#')[0];
  e.respondWith(fetch(r).then(function (resp) {
    if (resp && resp.ok) { var c = resp.clone(); caches.open(CACHE).then(function (k) { k.put(key, c); }); }
    return resp;
  }).catch(function () { return caches.match(key).then(function (m) { return m || caches.match(self.registration.scope); }); }));
});
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) { e.waitUntil(self.clients.claim()); });
self.addEventListener('push', function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'Fantasy Hockey', {
    body: d.body || '', icon: 'icon-192.png', badge: 'icon-192.png', tag: d.tag || 'fh-daily', data: { url: d.url || './' }
  }));
});
self.addEventListener('notificationclick', function (e) {
  e.notification.close();
  var target = new URL((e.notification.data && e.notification.data.url) || './', self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (list) {
    for (var i = 0; i < list.length; i++) {
      if (list[i].url.indexOf(self.registration.scope) === 0 && 'focus' in list[i]) { return list[i].focus(); }
    }
    return self.clients.openWindow(target);
  }));
});
