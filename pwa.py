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
        {"src": "icon-192-v4.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": "icon-512-v4.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": "icon-512-v4.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
}

SW = r"""/* Fantasy Hockey service worker: push alerts, an instant-opening app, and an offline copy.
   - app.<code>.js / .css and the icons never change under the same name, so they come straight from the phone.
   - the page and the data are network first, so you always get the newest when online. The saved copy is used
     only with no signal (or if the network takes more than 4 seconds).
   - version.json is never cached: the open app asks it every minute whether anything new is live. */
var CACHE = 'fh-v2';
function keyOf(u) { return u.split('?')[0].split('#')[0]; }
function save(key, resp) { if (resp && resp.ok) { var c = resp.clone(); caches.open(CACHE).then(function (k) { k.put(key, c); }); } return resp; }
function fromCache(key) { return caches.match(key).then(function (m) { return m || caches.match(self.registration.scope); }); }
self.addEventListener('fetch', function (e) {
  var r = e.request, u = new URL(r.url);
  if (r.method !== 'GET' || u.origin !== self.location.origin) return;
  if (/version\.json$/.test(u.pathname)) return;
  var key = keyOf(r.url);
  if (/\/app\.[0-9a-f]+\.(js|css)$|\.png$/.test(u.pathname)) {
    e.respondWith(caches.match(key).then(function (m) {
      return m || fetch(r).then(function (resp) {
        if (resp && resp.ok && /\/app\./.test(u.pathname)) {          /* a new app version: drop the old one's files */
          var ext = u.pathname.split('.').pop();
          caches.open(CACHE).then(function (k) { k.keys().then(function (ks) { ks.forEach(function (q) {
            var qp = new URL(q.url).pathname; if (/\/app\.[0-9a-f]+\./.test(qp) && qp.split('.').pop() === ext && qp !== u.pathname) k.delete(q); }); }); });
        }
        return save(key, resp);
      });
    }));
    return;
  }
  e.respondWith(new Promise(function (resolve) {
    var done = false;
    var net = fetch(r, { cache: 'no-store' }).then(function (resp) { return save(key, resp); });
    var t = setTimeout(function () { fromCache(key).then(function (m) { if (m && !done) { done = true; resolve(m); } }); }, 4000);
    net.then(function (resp) { if (!done) { done = true; clearTimeout(t); resolve(resp); } })
       .catch(function () { clearTimeout(t); fromCache(key).then(function (m) { if (!done) { done = true; resolve(m || Response.error()); } }); });
  }));
});
self.addEventListener('install', function (e) { self.skipWaiting(); });
self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});
self.addEventListener('push', function (e) {
  var d = {};
  try { d = e.data ? e.data.json() : {}; } catch (x) { d = { body: e.data ? e.data.text() : '' }; }
  e.waitUntil(self.registration.showNotification(d.title || 'Fantasy Hockey', {
    body: d.body || '', icon: 'icon-192-v4.png', badge: 'icon-192-v4.png', tag: d.tag || 'fh-daily', data: { url: d.url || './' }
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
    for name in ("apple-touch-icon-v4.png", "icon-192-v4.png", "icon-512-v4.png"):
        shutil.copyfile(src / name, out / name)
    (out / "manifest.webmanifest").write_text(json.dumps(MANIFEST, indent=2), encoding="utf-8")
    (out / "sw.js").write_text(SW, encoding="utf-8")
