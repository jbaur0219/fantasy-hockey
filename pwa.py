"""
Turns the site into an installable phone app (home-screen icon, opens full screen) and powers the push alerts.

  - write_files(): copies the icons and writes manifest.webmanifest + sw.js next to index.html
  - HEAD / APP_JS / APPBAR: what the page needs (patched in by build.py)
  - the service worker only handles pushes and taps. It never caches pages, so the app always shows the newest build.

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

SW = r"""/* Fantasy Hockey service worker: push alerts only, no caching (the app must always show the latest build). */
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

HEAD = (
    '<link rel="manifest" href="manifest.webmanifest">'
    '<link rel="apple-touch-icon" href="apple-touch-icon.png">'
    '<link rel="icon" type="image/png" href="icon-192.png">'
    '<meta name="apple-mobile-web-app-capable" content="yes">'
    '<meta name="mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-title" content="Fantasy Hockey">'
    '<meta name="apple-mobile-web-app-status-bar-style" content="default">'
    '<title>Fantasy Hockey Manager</title>'
)

APPBAR = '<div id="appbar"></div>'

APP_JS = r"""/* ---------- phone app: install hint + push alerts ---------- */
var APPKEY='BIUUEZQFmDcAdIOkdRLbYzUa0dwE69zLw65PNAYcu_K_j1Hi70WwzW8yXtJG3MtBN0_qC1rZ408ec5U1ETWG0kU';
function appStandalone(){return window.navigator.standalone===true||(window.matchMedia&&window.matchMedia('(display-mode: standalone)').matches);}
function appB64(s){var p='='.repeat((4-s.length%4)%4),b=(s+p).replace(/-/g,'+').replace(/_/g,'/'),r=atob(b),o=new Uint8Array(r.length);for(var i=0;i<r.length;i++)o[i]=r.charCodeAt(i);return o;}
function appBox(html){var el=document.getElementById('appbar');if(el)el.innerHTML=html?'<div class="card" style="margin:8px 0;padding:10px 14px">'+html+'</div>':'';}
function appRender(){
  var mobile=/iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
  var canPush=('serviceWorker' in navigator)&&('PushManager' in window)&&('Notification' in window);
  if(!canPush){
    appBox(mobile&&!appStandalone()?'<b>Get this as an app:</b> tap the Share button, choose <b>Add to Home Screen</b>, then open it from your home screen to turn on alerts.':'');
    return;
  }
  navigator.serviceWorker.ready.then(function(reg){
    return reg.pushManager.getSubscription().then(function(sub){
      if(Notification.permission==='denied'){appBox('<span class="muted">Alerts are blocked. On iPhone: Settings, Notifications, Fantasy Hockey.</span>');return;}
      if(!sub){
        appBox('<b>Daily alerts:</b> get the day\'s best move on your phone each morning. <button class="chip-btn" id="appOn" style="margin-left:6px">Turn on alerts</button><span id="appMsg" class="muted"></span>');
        var b=document.getElementById('appOn');
        if(b)b.addEventListener('click',function(){
          var m=document.getElementById('appMsg');
          Notification.requestPermission().then(function(p){
            if(p!=='granted'){if(m)m.textContent=' Not allowed.';return;}
            return reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:appB64(APPKEY)}).then(appRender);
          }).catch(function(e){if(m)m.textContent=' Could not turn on alerts ('+(e&&e.message||e)+').';});
        });
        return;
      }
      var code=JSON.stringify(sub);
      appBox('&#128276; <b>Alerts are on for this phone.</b> <button class="chip-btn" id="appCopy" style="margin-left:6px">Copy phone code</button><span id="appMsg" class="muted"></span>'
        +'<div class="muted" style="margin-top:4px">The phone code is only needed once, to link this phone to the daily build.</div>'
        +'<textarea id="appCode" readonly rows="3" style="display:none;width:100%;margin-top:6px;font-size:11px">'+esc(code)+'</textarea>');
      var c=document.getElementById('appCopy');
      if(c)c.addEventListener('click',function(){
        var m=document.getElementById('appMsg'),t=document.getElementById('appCode');
        var show=function(){t.style.display='block';t.focus();t.select();if(m)m.textContent=' Select all and copy.';};
        if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(code).then(function(){if(m)m.textContent=' Copied.';},show);}else{show();}
      });
    });
  }).catch(function(){});
}
function appStart(){
  if('serviceWorker' in navigator){try{navigator.serviceWorker.register('sw.js').then(appRender,appRender);}catch(e){appRender();}}else{appRender();}
}

/* ---------- tabs + startup ---------- */"""


def write_files(site_dir="site"):
    out = Path(site_dir)
    out.mkdir(exist_ok=True)
    src = Path(__file__).parent / "pwa"
    for name in ("apple-touch-icon.png", "icon-192.png", "icon-512.png"):
        shutil.copyfile(src / name, out / name)
    (out / "manifest.webmanifest").write_text(json.dumps(MANIFEST, indent=2), encoding="utf-8")
    (out / "sw.js").write_text(SW, encoding="utf-8")


def page_patches():
    """(page_patches, js_patches) to feed build.patch_text."""
    js = APP_JS.replace("BIUUEZQFmDcAdIOkdRLbYzUa0dwE69zLw65PNAYcu_K_j1Hi70WwzW8yXtJG3MtBN0_qC1rZ408ec5U1ETWG0kU", VAPID_PUBLIC)
    return (
        [("<title>Fantasy Hockey Manager</title>", HEAD),
         ('<div id="lockbar"', APPBAR + '<div id="lockbar"')],
        [("/* ---------- tabs + startup ---------- */", js),
         ("LK.start();", "LK.start();\nappStart();")],
    )
