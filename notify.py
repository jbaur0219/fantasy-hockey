#!/usr/bin/env python3
"""
Sends a push notification to the phone(s) linked in PUSH_CONFIG.

`send(cfg, payload)` is the one place that talks to the phone makers' push services. It returns one result per phone
(did it go, the HTTP code, and the push service's own reason when it refused), so the server can show what happened
instead of guessing. The command line (python notify.py payload.json) is kept for older callers; it never fails a build.

PUSH_CONFIG is JSON: {"vapid_private": "<key>", "subscriptions": [<phone code>, ...]}
"""
import json
import os
import sys
from pathlib import Path

CLAIM = {"sub": "mailto:jbaur0219@users.noreply.github.com"}


def _reason(e):
    """The push service's own words for refusing (Apple says things like BadJwtToken or BadDeviceToken)."""
    resp = getattr(e, "response", None)
    code = getattr(resp, "status_code", None)
    text = ""
    try:
        text = (resp.text or "").strip()[:160] if resp is not None else ""
    except Exception:
        pass
    return code, text or str(e)[:160]


def send(cfg, payload):
    """Push `payload` (title, body, url, tag) to every phone in cfg. Returns [{endpoint, ok, code, detail}]."""
    from pywebpush import webpush, WebPushException
    subs = cfg.get("subscriptions") or ([cfg["subscription"]] if cfg.get("subscription") else [])
    out = []
    for sub in subs:
        ep = str(sub.get("endpoint", ""))
        try:
            r = webpush(subscription_info=sub, data=json.dumps(payload), vapid_private_key=cfg["vapid_private"],
                        vapid_claims=dict(CLAIM), ttl=6 * 3600)
            out.append({"endpoint": ep, "ok": True, "code": getattr(r, "status_code", None), "detail": ""})
        except WebPushException as e:
            code, detail = _reason(e)
            out.append({"endpoint": ep, "ok": False, "code": code, "detail": detail,
                        "dead": code in (404, 410)})        # the phone removed the alert link: it has to be linked again
        except Exception as e:                                  # one bad phone never stops the others
            out.append({"endpoint": ep, "ok": False, "code": None, "detail": f"{type(e).__name__}: {e}"[:160]})
    return out


def main():
    cfg_raw = os.environ.get("PUSH_CONFIG", "").strip()
    if not cfg_raw:
        print("No PUSH_CONFIG secret set, so no alert sent.")
        return
    payload_path = Path(sys.argv[1] if len(sys.argv) > 1 else "notify_payload.json")
    if not payload_path.exists():
        print("No notify_payload.json from the build, so no alert sent.")
        return
    try:
        cfg = json.loads(cfg_raw)
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        res = send(cfg, payload)
        if not res:
            print("PUSH_CONFIG has no phone linked yet.")
            return
        for r in res:
            if not r["ok"]:
                note = " (the phone's alert link expired)" if r.get("dead") else ""
                print(f"::warning::Push failed ({r['code']}): {r['detail']}{note}")
        print(f"Alert sent to {sum(r['ok'] for r in res)} of {len(res)} phone(s): {payload.get('title')} | {payload.get('body')}")
    except Exception as e:                      # never break the daily build over an alert
        print(f"::warning::Alert step skipped ({type(e).__name__}: {e})")


if __name__ == "__main__":
    main()
    sys.exit(0)
