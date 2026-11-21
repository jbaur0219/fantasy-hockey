#!/usr/bin/env python3
"""Open a built page in headless Chrome at iPhone size, visit every tab, report script errors and save screenshots.

python tools/smoke.py site/index.html [screenshot_dir]
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

TABS = ["today", "moves/plan", "moves/swap", "moves/streams", "roster/team", "roster/week", "players",
        "league/games", "league/table", "league/trade", "league/help"]


def main(page_path, shots=None):
    url = pathlib.Path(page_path).resolve().as_uri()
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        ctx = b.new_context(viewport={"width": 402, "height": 874}, device_scale_factor=2, is_mobile=True, has_touch=True)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(f"page error: {e}"))
        pg.on("console", lambda m: errors.append(f"console {m.type}: {m.text}") if m.type == "error" and "Failed to load resource" not in m.text else None)
        pg.route("**/*", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())   # offline: no photos
        pg.goto(url + "#today")
        pg.wait_for_timeout(600)
        out = {}
        for t in TABS:
            pg.evaluate(f"document.querySelector('[data-go=\"{t.split('/')[0]}\"]').click()")
            if "/" in t:
                pg.evaluate(f"var b=document.querySelector('#snav [data-go=\"{t}\"]');if(b)b.click();")
            pg.wait_for_timeout(250)
            info = pg.evaluate("""()=>{var v=document.querySelector('.usub.on');if(!v)return null;
              return {h:document.body.scrollHeight,cards:[...v.querySelectorAll('.card')].map(c=>c.getAttribute('data-ut')+(c.classList.contains('closed')?' [closed]':''))};}""")
            out[t] = info
            if shots:
                pg.screenshot(path=f"{shots}/{t.replace('/', '_')}.png", full_page=False)
        b.close()
    for t, i in out.items():
        print(f"{t:15} {i}")
    print("\n".join(errors) if errors else "no script errors")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
