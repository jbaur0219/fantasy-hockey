"""python tools/qa/perf.py  (after tools/qa/page.py). Measure what each interaction costs: layouts/style recalcs during the animation, long frames, worst frame.
4x CPU slowdown approximates a phone. Per-frame layout during an animation is the thing to hunt."""
import json, sys
from playwright.sync_api import sync_playwright

PAGE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fhqa/page.html"
SCHEME = sys.argv[2] if len(sys.argv) > 2 else "light"

REC = r"""() => { window.__fr = []; let last = performance.now(); window.__on = true;
  (function tick(t){ window.__fr.push(t - last); last = t; if (window.__on) requestAnimationFrame(tick); })(performance.now()); }"""
STOP = r"""() => { window.__on = false; const f = window.__fr.slice(2); const long = f.filter(x => x > 20).length;
  return {frames: f.length, long, worst: Math.round(Math.max(0, ...f)), avg: +(f.reduce((a,b)=>a+b,0)/Math.max(1,f.length)).toFixed(1)}; }"""

def clicktext(sel, txt):
    return f"""() => {{ for (const b of document.querySelectorAll({json.dumps(sel)})) if ((b.textContent||'').trim().startsWith({json.dumps(txt)})) {{ b.click(); return true; }} return false; }}"""

with sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=3, is_mobile=True, has_touch=True, color_scheme=SCHEME)
    pg = ctx.new_page()
    import base64 as _b
    _img = _b.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    ctx.route(lambda u: not u.startswith("file:"), lambda r: r.fulfill(status=200, content_type="image/png", body=_img) if r.request.resource_type == "image" else r.fulfill(status=200, body="{}", content_type="application/json"))
    cdp = ctx.new_cdp_session(pg)
    cdp.send("Performance.enable")
    pg.goto("file://" + PAGE + "#today")
    pg.wait_for_timeout(2500)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})

    def metrics():
        m = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
        return m

    out = {}
    def measure(name, js, settle=200, window=900):
        pg.wait_for_timeout(settle)
        pg.evaluate(REC)
        m0 = metrics()
        ok = pg.evaluate(js) if js else True
        pg.wait_for_timeout(120)          # the click's own work (first layout) is allowed
        m1 = metrics()
        pg.wait_for_timeout(window)      # the animation: should need no further layouts
        m2 = metrics()
        fr = pg.evaluate(STOP)
        out[name] = dict(ok=ok, **fr,
                         layouts_click=int(m1["LayoutCount"] - m0["LayoutCount"]),
                         layouts_anim=int(m2["LayoutCount"] - m1["LayoutCount"]),
                         recalc_anim=int(m2["RecalcStyleCount"] - m1["RecalcStyleCount"]),
                         layout_ms=round((m2["LayoutDuration"] - m0["LayoutDuration"]) * 1000),
                         style_ms=round((m2["RecalcStyleDuration"] - m0["RecalcStyleDuration"]) * 1000),
                         script_ms=round((m2["ScriptDuration"] - m0["ScriptDuration"]) * 1000))

    measure("idle", None)
    measure("tab Moves", clicktext("#bnav button", "Moves"))
    measure("sub Swap lab", clicktext("#snav button", "Swap lab"))
    measure("sub Streams", clicktext("#snav button", "Streams"))
    measure("tab Roster", clicktext("#bnav button", "Roster"))
    measure("roster day tap", "() => { const b = document.querySelectorAll('.rd-d'); if (b.length) { b[1].click(); return true; } return false; }")
    measure("roster All stats", clicktext("#rosterSeg button, .seg button, button", "All stats"))
    measure("sub Schedule", clicktext("#snav button", "Schedule"))
    measure("scroll Schedule", "() => { window.scrollTo({top: 900, behavior: 'smooth'}); return true; }", window=1200)
    measure("tab League", clicktext("#bnav button", "League"))
    measure("tab Today", clicktext("#bnav button", "Today"))
    measure("collapse Track record", "() => { const h = document.querySelector('.card[data-ut=\"Track record\"] > h2'); if (!h) return false; h.click(); return true; }")
    measure("expand Track record", "() => { const h = document.querySelector('.card[data-ut=\"Track record\"] > h2'); if (!h) return false; h.click(); return true; }")
    measure("open matchup sheet", "() => { const c = document.querySelector('.sb, .sbc, [class*=sb-]'); const t = c && c.closest('button,[role=button],.card,div'); (t||c).click(); return !!c; }", window=1000)
    measure("close sheet", "() => { const m = document.getElementById('modal'); if (!m) return false; const x = m.querySelector('.mu-x,.x,[aria-label=Close],button.close'); if (x) { x.click(); return 'x'; } m.click(); return 'bg'; }", window=900)
    measure("tab Moves again", clicktext("#bnav button", "Moves"))
    measure("sub Game plan", clicktext("#snav button", "Game plan"))
    measure("expand move row", "() => { const r = document.querySelector('.grp>.row[data-exp], .mv-row, [data-exp]'); if (!r) return false; r.click(); return true; }")
    measure("open player card", "() => { const a = document.querySelector('[id^=\"v-\"].on a.pl'); if (!a) return false; a.click(); return true; }", window=1000)
    measure("close player card", "() => { const m = document.getElementById('modal'); const x = m && m.querySelector('.mx,.x,[aria-label=Close],button.close'); if (x) { x.click(); return 'x'; } if (m) m.click(); return 'bg'; }")
    print("%-24s %6s %5s %5s %7s %7s %7s" % ("step", "frames", "long", "worst", "lay/clk", "lay/anim", "lay ms"))
    for k, v in out.items():
        print("%-24s %6s %5s %5s %7s %7s %7s" % (k, v["frames"], v["long"], v["worst"], v["layouts_click"], v["layouts_anim"], v["layout_ms"]))
    print("lay/anim should stay near 0: a layout on every animation frame is a hitch on the phone.")
    br.close()
