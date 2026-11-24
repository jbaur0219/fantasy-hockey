#!/usr/bin/env python3
"""Run the backtest offline on a copy of the history folder (the live one is on the Railway volume /data/history).

  python tools/backtest.py                 # this repo's history/ (a stale copy; the live log is on the server)
  python tools/backtest.py path/to/history --write   # also write backtest.json / backtest.md into that folder
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import backtest as BT   # noqa: E402


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    hist = Path(args[0]) if args else Path(__file__).resolve().parent.parent / "history"
    a = BT.analyze(BT.rows(BT.read_log(hist / "moves.jsonl"), None, BT.actuals_offline(hist)))
    if "--json" in argv:
        print(json.dumps(a, indent=1))
    else:
        print(BT.markdown(a))
    if "--write" in argv:
        (hist / "backtest.json").write_text(json.dumps(a, indent=1), encoding="utf-8")
        (hist / "backtest.md").write_text(BT.markdown(a), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:])
