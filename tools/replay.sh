#!/bin/sh
# Rebuild the page from a saved snapshot, offline:  sh tools/replay.sh snapshot.json.gz [plan_state.json] [out.html]
SNAP=$1; PS=${2:-}; OUT=${3:-site/index.html}
cp plan_state.json /tmp/_ps_backup.json 2>/dev/null
[ -n "$PS" ] && cp "$PS" plan_state.json
ESPN_S2=replay SWID=replay FH_REPLAY="$SNAP" python3 build.py
RC=$?
[ "$OUT" != site/index.html ] && cp site/index.html "$OUT"
cp /tmp/_ps_backup.json plan_state.json 2>/dev/null
exit $RC
