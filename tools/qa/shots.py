"""python tools/qa/shots.py  (after tools/qa/page.py). Screenshot every view of the replayed app at iPhone 16 Pro size, light + dark, and report layout problems."""
import json, sys, pathlib
from playwright.sync_api import sync_playwright

PAGE = sys.argv[1] if len(sys.argv) > 1 else "/tmp/fhqa/page.html"
OUT = pathlib.Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/fhqa/shots")
OUT.mkdir(parents=True, exist_ok=True)
VIEWS = ["today/main", "moves/plan", "moves/swap", "moves/streams", "roster/team", "roster/week",
         "players/main", "league/games", "league/table", "league/trade", "league/help"]

CHECK = r"""() => {
  const vw = document.documentElement.clientWidth, bad = [];
  const sw = document.documentElement.scrollWidth;
  for (const el of document.querySelectorAll('[id^="v-"].on *')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    // skip things inside deliberate sideways scrollers
    let p = el.parentElement, inScroll = false;
    while (p) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll') { inScroll = true; break; } p = p.parentElement; }
    if (!inScroll && (r.right > vw + 0.5 || r.left < -0.5) && !el.closest('#bnav,#gnav,.gn-edge'))
      bad.push({k: 'offscreen', t: el.tagName + '.' + el.className, txt: (el.textContent || '').trim().slice(0, 40), l: Math.round(r.left), r: Math.round(r.right)});
    if (el.children.length === 0 && el.scrollWidth > el.clientWidth + 1 && cs.overflow === 'hidden' && cs.textOverflow !== 'ellipsis')
      bad.push({k: 'clipped', t: el.tagName + '.' + el.className, txt: (el.textContent || '').trim().slice(0, 40)});
  }
  return {sw, vw, bad: bad.slice(0, 25), n: bad.length};
}"""

with sync_playwright() as pw:
    b = pw.chromium.launch()
    rep = {}
    for scheme in ("light", "dark"):
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True,
                            has_touch=True, color_scheme=scheme)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.clock.install(time=1795223377822/1000)
        pg.goto("file://" + PAGE + "#today")
        pg.clock.run_for(2000); pg.wait_for_timeout(800)
        for v in VIEWS:
            tab, sub = v.split("/")
            lab = {"today":"Today","moves":"Moves","roster":"Roster","players":"Players","league":"League"}[tab]
            pg.evaluate("l => { for (const b of document.querySelectorAll('#bnav button')) if ((b.textContent||'').trim()===l) { b.click(); return; } }", lab)
            pg.wait_for_timeout(700)
            sublab = {"plan":"Game plan","swap":"Swap lab","streams":"Streams","team":"My team","week":"Schedule","games":"Matchups","table":"Standings","trade":"Trade lab","help":"Help"}.get(sub)
            if sublab: pg.evaluate("l => { for (const b of document.querySelectorAll('#snav button')) if ((b.textContent||'').trim()===l) { b.click(); return; } }", sublab)
            pg.clock.run_for(1500)
            pg.wait_for_timeout(900)
            pg.evaluate("window.scrollTo(0,0)")
            pg.wait_for_timeout(300)
            name = v.replace("/", "_") + "_" + scheme
            pg.screenshot(path=str(OUT / (name + ".png")), full_page=True)
            rep[name] = pg.evaluate(CHECK)
        rep["errors_" + scheme] = errs
        ctx.close()
    b.close()
print(json.dumps(rep, indent=1))
