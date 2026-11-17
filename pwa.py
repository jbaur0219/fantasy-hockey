"""
Turns the site into an installable phone app (home-screen icon, opens full screen) and powers the push alerts.

  - write_files(): copies the icons and writes manifest.webmanifest + sw.js next to index.html
  - the install hint and the alert switch live in web/app.js (they use VAPID_PUBLIC below)
  - the service worker handles pushes and taps, and keeps a fallback copy of the page for when there is no signal
    (network first, so the app always shows the newest build when online).

The public key below is safe to publish. The matching private key lives only in the PUSH_CONFIG secret.
"""
import json
import shutil
from pathlib import Path

VAPID_PUBLIC = "BIUUEZQFmDcAdIOkdRLbYzUa0dwE69zLw65PNAYcu_K_j1Hi70WwzW8yXtJG3MtBN0_qC1rZ408ec5U1ETWG0kU"

MANIFEST = {
    "name": "Fantasy Hockey Manager",
    "short_name": "Fantasy Hockey",
    "description": "Daily streams, move plan and lineup help for my ESPN hockey team",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "orientation": "portrait",
    "background_color": "#0b1d3a",
    "theme_color": "#0b1d3a",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}

SW = r"""/* Fantasy Hockey service worker: push alerts, plus a fallback copy of the page.
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
"""

def write_files(site_dir="site"):
    out = Path(site_dir)
    out.mkdir(exist_ok=True)
    src = Path(__file__).parent / "pwa"
    for name in ("apple-touch-icon.png", "icon-192.png", "icon-512.png"):
        shutil.copyfile(src / name, out / name)
    (out / "manifest.webmanifest").write_text(json.dumps(MANIFEST, indent=2), encoding="utf-8")
    (out / "sw.js").write_text(SW, encoding="utf-8")
