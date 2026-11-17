#!/usr/bin/env python3
"""
Sends the morning push notification to the phone(s) linked in the PUSH_CONFIG secret.

build.py writes notify_payload.json (title, body, url). The workflow runs this after a successful deploy, only for
"morning" builds. It never fails the build: any problem is printed as a warning and the script exits 0.

PUSH_CONFIG is JSON: {"vapid_private": "<key>", "subscriptions": [<phone code>, ...]}
"""
import json
import os
import sys
from pathlib import Path


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
        from pywebpush import webpush, WebPushException
        cfg = json.loads(cfg_raw)
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        subs = cfg.get("subscriptions") or ([cfg["subscription"]] if cfg.get("subscription") else [])
        if not subs:
            print("PUSH_CONFIG has no phone linked yet.")
            return
        sent = 0
        for sub in subs:
            try:
                webpush(subscription_info=sub, data=json.dumps(payload),
                        vapid_private_key=cfg["vapid_private"],
                        vapid_claims={"sub": "mailto:jbaur0219@users.noreply.github.com"}, ttl=6 * 3600)
                sent += 1
            except WebPushException as e:
                code = getattr(getattr(e, "response", None), "status_code", None)
                if code in (404, 410):
                    print("::warning::That phone's alert link has expired. Open the app, turn alerts on again and send a new phone code.")
                else:
                    print(f"::warning::Push failed ({code}): {e}")
        print(f"Alert sent to {sent} of {len(subs)} phone(s): {payload.get('title')} | {payload.get('body')}")
    except Exception as e:                      # never break the daily build over an alert
        print(f"::warning::Alert step skipped ({type(e).__name__}: {e})")


if __name__ == "__main__":
    main()
    sys.exit(0)
