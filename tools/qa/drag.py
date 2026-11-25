"""python tools/qa/drag.py  (after tools/qa/page.py). Finger drags with real touch events (CDP), 4x CPU slowdown: layouts and long frames during the drag and the settle."""
from playwright.sync_api import sync_playwright

PAGE = "/tmp/fhqa/page.html"

def tap(pg, js):
    pg.evaluate(js); pg.wait_for_timeout(900)

with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True)
    ctx.route(lambda u: not u.startswith("file:"), lambda r: r.abort())
    pg = ctx.new_page(); cdp = ctx.new_cdp_session(pg); cdp.send("Performance.enable")
    pg.goto("file://" + PAGE + "#today"); pg.wait_for_timeout(2500)
    def M(): return {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
    def drag(name, x0, y0, x1, y1, steps=24, settle=900):
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
        pg.evaluate("() => { window.__fr=[]; let l=performance.now(); window.__on=true; (function t(n){ window.__fr.push(n-l); l=n; if(window.__on) requestAnimationFrame(t); })(performance.now()); }")
        m0 = M()
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x0, "y": y0}]})
        for i in range(1, steps + 1):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x0 + (x1 - x0) * i / steps, "y": y0 + (y1 - y0) * i / steps}]})
            pg.wait_for_timeout(16)
        m1 = M()
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        pg.wait_for_timeout(settle)
        m2 = M()
        fr = pg.evaluate("() => { window.__on=false; const f=window.__fr.slice(2); return {long: f.filter(x=>x>20).length, worst: Math.round(Math.max(0,...f)), n: f.length}; }")
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
        print(f"{name:28s} drag layouts {int(m1['LayoutCount']-m0['LayoutCount']):3d} ({(m1['LayoutDuration']-m0['LayoutDuration'])*1000:5.1f} ms)  settle layouts {int(m2['LayoutCount']-m1['LayoutCount']):3d}  frames {fr}")
    drag("pull past top (bounce)", 200, 300, 200, 560)
    drag("scroll up (finger up)", 200, 700, 200, 200, steps=12)
    tap(pg, "() => { for (const b of document.querySelectorAll('#bnav button')) if ((b.textContent||'').trim()==='Roster') b.click(); }")
    pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(400)
    y = pg.evaluate("() => { const b = document.getElementById('rdBody'); if (!b) return null; const r = b.getBoundingClientRect(); return Math.min(700, r.top + 120); }")
    print("rdBody at", y)
    if y: drag("roster swipe to next day", 320, y, 80, y + 6)
    tap(pg, "() => { for (const b of document.querySelectorAll('#bnav button')) if ((b.textContent||'').trim()==='Today') b.click(); }")
    pg.evaluate("window.scrollTo(0,0)"); pg.wait_for_timeout(400)
    tap(pg, "() => { const c = document.querySelector('[data-mu]'); if (c) c.click(); }")
    pg.wait_for_timeout(600)
    drag("matchup swipe next", 330, 330, 60, 336)
    drag("matchup swipe back", 60, 330, 330, 336)
    drag("sheet pull down to close", 200, 140, 200, 640, steps=20)
    pg.wait_for_timeout(500)
    print("sheet still open:", pg.evaluate("() => !!document.querySelector('#modal.open')"),
          " html.sheet-on left:", pg.evaluate("() => document.documentElement.classList.contains('sheet-on')"))
    br.close()
