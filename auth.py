#!/usr/bin/env python3
"""
ACCOUNTS AND SIGN-IN for the always-on server (server.py). Nothing here talks to ESPN.

How it works
  - Accounts live on the volume (DATA_DIR/users.json): a name, a role (owner or member) and a scrypt password hash.
    Passwords are never stored or logged.
  - The owner account comes from Railway Variables OWNER_USER and OWNER_PASSWORD (created on boot, password updated if
    the variable changes). Members join with a one-time invite code the owner makes (POST /api/invite).
  - Signing in sets one cookie (fh_s): a random 256-bit token, HttpOnly, Secure, SameSite=Lax, good for 180 days and
    renewed while in use, so the home-screen app stays signed in. Only a SHA-256 of each token is stored
    (DATA_DIR/sessions.json), so a copy of the volume can't be used to sign in.
  - Wrong passwords are rate limited per address and per account (MAX_FAILS in FAIL_WINDOW).
  - The server only REQUIRES sign-in when AUTH=1 (Railway Variables). Until then the app works exactly as before, and
    signing in is only needed for the owner's private pages (/admin/backtest, /admin/lifetime).

Each account can carry its own league settings (platform, league id, team id) for when builds run per user; today
every account sees the owner's league (see claude/railway-setup.md, "Multi-user").
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

COOKIE = "fh_s"
SESSION_DAYS = 180
RENEW_DAYS = 7                     # renew a session's expiry at most once a week (fewer writes)
INVITE_DAYS = 7
MAX_FAILS = 8                      # wrong passwords allowed per address and per account...
FAIL_WINDOW = 15 * 60              # ...in this many seconds
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,31}$")
MIN_PW, MAX_PW = 8, 200


def _b(x):
    return x.hex()


def hash_password(pw, salt=None):
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode("utf-8"), salt=salt, dklen=32, **SCRYPT)
    return f"scrypt${SCRYPT['n']}${SCRYPT['r']}${SCRYPT['p']}${_b(salt)}${_b(h)}"


def check_password(pw, stored):
    try:
        kind, n, r, p, salt, h = stored.split("$")
        if kind != "scrypt":
            return False
        got = hashlib.scrypt(pw.encode("utf-8"), salt=bytes.fromhex(salt), dklen=32, n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(got.hex(), h)
    except Exception:
        return False


def _tok_hash(tok):
    return hashlib.sha256(tok.encode("utf-8")).hexdigest()


def norm_name(name):
    return str(name or "").strip().lower()


class Auth:
    def __init__(self, data_dir, now=time.time):
        self.dir = Path(data_dir)
        self.now = now
        self.lock = threading.Lock()
        self.fails = {}                       # key -> [timestamps]
        # a password check is slow on purpose; this dummy hash keeps "no such user" just as slow
        self._dummy = hash_password(secrets.token_hex(8))

    # ------------------------------------------------------------ storage
    def _read(self, name, default):
        try:
            return json.loads((self.dir / name).read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write(self, name, obj):
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.dir / name
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, p)

    def users(self):
        return self._read("users.json", {})

    def has_owner(self):
        return any(u.get("role") == "owner" for u in self.users().values())

    # ------------------------------------------------------------ accounts
    def add_user(self, name, pw, role="member", league=None):
        name = norm_name(name)
        if not NAME_RE.match(name):
            raise ValueError("Names are 3 to 32 letters, numbers, dots, dashes or underscores.")
        if not (MIN_PW <= len(pw or "") <= MAX_PW):
            raise ValueError(f"Passwords need at least {MIN_PW} characters.")
        with self.lock:
            us = self.users()
            if name in us:
                raise ValueError("That name is taken.")
            us[name] = {"role": role, "pw": hash_password(pw), "created": int(self.now()),
                        "league": league or {}}
            self._write("users.json", us)
        return name

    def ensure_owner(self, name, pw):
        """The owner account from OWNER_USER / OWNER_PASSWORD: made if missing, password updated if it changed."""
        name = norm_name(name)
        if not name or not pw:
            return None
        with self.lock:
            us = self.users()
            u = us.get(name)
            if u and u.get("role") == "owner" and check_password(pw, u.get("pw", "")):
                return name
        if u is None:
            return self.add_user(name, pw, role="owner")
        if len(pw) < MIN_PW:
            raise ValueError(f"OWNER_PASSWORD needs at least {MIN_PW} characters.")
        with self.lock:
            us = self.users()
            us[name].update(role="owner", pw=hash_password(pw))
            self._write("users.json", us)
            self._drop_sessions(name)             # a new password signs every device out
        return name

    def set_league(self, name, league):
        with self.lock:
            us = self.users()
            if norm_name(name) not in us:
                raise ValueError("No such account.")
            us[norm_name(name)]["league"] = {k: str(v)[:40] for k, v in (league or {}).items()
                                            if k in ("platform", "league_id", "team_id", "season")}
            self._write("users.json", us)

    # ------------------------------------------------------------ rate limit
    def _limited(self, *keys):
        t = self.now()
        for k in keys:
            self.fails[k] = [x for x in self.fails.get(k, []) if t - x < FAIL_WINDOW]
            if len(self.fails[k]) >= MAX_FAILS:
                return True
        return False

    def _fail(self, *keys):
        t = self.now()
        if len(self.fails) > 5000:                # many addresses: forget the ones with nothing recent
            self.fails = {k: v for k, v in self.fails.items() if v and t - v[-1] < FAIL_WINDOW}
        for k in keys:
            self.fails.setdefault(k, []).append(t)

    # ------------------------------------------------------------ sessions
    def login(self, name, pw, ip="?"):
        """(token, None) or (None, reason). reason is 'bad' or 'slow down'."""
        name = norm_name(name)
        keys = ("ip:" + str(ip), "user:" + name)
        if self._limited(*keys):
            return None, "slow down"
        u = self.users().get(name)
        ok = check_password(pw or "", u["pw"] if u else self._dummy)
        if not (u and ok):
            self._fail(*keys)
            return None, "bad"
        tok = secrets.token_urlsafe(32)
        with self.lock:
            ss = self._read("sessions.json", {})
            t = self.now()
            ss = {k: v for k, v in ss.items() if v.get("exp", 0) > t}
            ss[_tok_hash(tok)] = {"user": name, "exp": int(t + SESSION_DAYS * 86400), "made": int(t)}
            self._write("sessions.json", ss)
        return tok, None

    def session(self, tok):
        """The signed-in account {'name', 'role', 'league'} for a cookie token, or None."""
        if not tok or len(tok) > 100:
            return None
        h = _tok_hash(tok)
        ss = self._read("sessions.json", {})
        s = ss.get(h)
        t = self.now()
        if not s or s.get("exp", 0) <= t:
            return None
        u = self.users().get(s["user"])
        if not u:
            return None
        if s["exp"] - t < (SESSION_DAYS - RENEW_DAYS) * 86400:      # in use: push the expiry out again
            with self.lock:
                ss = self._read("sessions.json", {})
                if h in ss:
                    ss[h]["exp"] = int(t + SESSION_DAYS * 86400)
                    self._write("sessions.json", ss)
        return {"name": s["user"], "role": u.get("role", "member"), "league": u.get("league") or {}}

    def logout(self, tok):
        if not tok:
            return
        with self.lock:
            ss = self._read("sessions.json", {})
            if ss.pop(_tok_hash(tok), None) is not None:
                self._write("sessions.json", ss)

    def _drop_sessions(self, name):
        ss = self._read("sessions.json", {})
        ss = {k: v for k, v in ss.items() if v.get("user") != name}
        self._write("sessions.json", ss)

    # ------------------------------------------------------------ invites
    def invite(self, by):
        code = "-".join(secrets.token_hex(2) for _ in range(3))     # e.g. 4f1a-09bc-77de: easy to read out
        with self.lock:
            inv = {k: v for k, v in self._read("invites.json", {}).items() if v.get("exp", 0) > self.now()}
            inv[_tok_hash(code)] = {"by": by, "exp": int(self.now() + INVITE_DAYS * 86400)}
            self._write("invites.json", inv)
        return code

    def signup(self, code, name, pw, ip="?"):
        """(token, None) or (None, message). The invite is used up only when the account is made."""
        if self._limited("ip:" + str(ip)):
            return None, "Too many tries. Wait a few minutes."
        h = _tok_hash(str(code or "").strip().lower())
        inv = self._read("invites.json", {})
        if h not in inv or inv[h].get("exp", 0) <= self.now():
            self._fail("ip:" + str(ip))
            return None, "That invite code isn't valid."
        try:
            self.add_user(name, pw)
        except ValueError as e:
            return None, str(e)
        with self.lock:
            inv = self._read("invites.json", {})
            inv.pop(h, None)
            self._write("invites.json", inv)
        return self.login(name, pw, ip)[0], None


def cookie_header(tok, secure=True, clear=False):
    attrs = ["Path=/", "HttpOnly", "SameSite=Lax"] + (["Secure"] if secure else [])
    if clear:
        return f"{COOKIE}=; Max-Age=0; " + "; ".join(attrs)
    return f"{COOKIE}={tok}; Max-Age={SESSION_DAYS * 86400}; " + "; ".join(attrs)


def token_from(cookie_hdr):
    for part in str(cookie_hdr or "").split(";"):
        k, _, v = part.strip().partition("=")
        if k == COOKIE:
            return v
    return None


# ------------------------------------------------------------ the sign-in page (served by server.py)
LOGIN_PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="color-scheme" content="light dark"><title>Sign in</title>
<style>
:root{--bg:#f2f2f7;--card:#fff;--tx:#000;--mut:#8e8e93;--sep:rgba(60,60,67,.29);--acc:#007aff;--bad:#ff3b30}
@media (prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--tx:#fff;--mut:#8e8e93;--sep:rgba(84,84,88,.65);--acc:#0a84ff;--bad:#ff453a}}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
html,body{margin:0;background:var(--bg);color:var(--tx);font:17px/1.3 -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif;-webkit-text-size-adjust:100%}
main{max-width:430px;margin:0 auto;padding:calc(env(safe-area-inset-top) + 56px) 16px calc(env(safe-area-inset-bottom) + 24px)}
h1{font-size:34px;font-weight:700;letter-spacing:.37px;margin:0 4px 6px}
p.sub{color:var(--mut);font-size:15px;margin:0 4px 22px}
.grp{background:var(--card);border-radius:12px;overflow:hidden;margin-bottom:22px}
.grp label{display:flex;align-items:center;min-height:44px;padding:0 16px;position:relative}
.grp label+label:before{content:"";position:absolute;top:0;left:16px;right:0;height:.5px;background:var(--sep)}
.grp span{width:96px;flex:none}
.grp input{flex:1;min-width:0;border:0;background:transparent;color:var(--tx);font:inherit;padding:11px 0;outline:none}
button{width:100%;min-height:50px;border:0;border-radius:12px;background:var(--acc);color:#fff;font:600 17px -apple-system,system-ui,sans-serif;transition:opacity .2s}
button:active{opacity:.6}button[disabled]{opacity:.45}
.msg{min-height:20px;color:var(--bad);font-size:15px;margin:12px 4px 0;text-align:center}
.alt{display:block;margin:22px auto 0;background:none;color:var(--acc);font-weight:400;width:auto;min-height:44px;padding:0 12px}
#su{display:none}body.su #su{display:flex}body:not(.su) #su+label:before{display:none}
</style></head><body><main>
<h1 id="t">Sign in</h1><p class="sub" id="s">Fantasy Hockey</p>
<form id="f" autocomplete="on" novalidate>
<div class="grp">
<label id="su"><span>Invite code</span><input name="code" autocomplete="one-time-code" autocapitalize="none" spellcheck="false"></label>
<label><span>Name</span><input name="name" autocomplete="username" autocapitalize="none" spellcheck="false" required></label>
<label><span>Password</span><input name="pw" type="password" autocomplete="current-password" required></label>
</div>
<button id="go" type="submit">Sign In</button>
<div class="msg" id="m" role="alert"></div>
</form>
<button class="alt" id="sw" type="button">Have an invite code?</button>
</main><script>
(function(){var f=document.getElementById('f'),m=document.getElementById('m'),go=document.getElementById('go'),su=false;
document.getElementById('sw').onclick=function(){su=!su;document.body.classList.toggle('su',su);m.textContent='';document.getElementById('t').textContent=su?'Join':'Sign in';go.textContent=su?'Create Account':'Sign In';this.textContent=su?'I already have an account':'Have an invite code?';f.pw.autocomplete=su?'new-password':'current-password';if(su)f.code.focus();};
f.onsubmit=function(e){e.preventDefault();m.textContent='';go.disabled=true;
var b={name:f.name.value,password:f.pw.value};if(su)b.code=f.code.value;
fetch(su?'api/signup':'api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b),credentials:'same-origin'})
.then(function(r){return r.json().then(function(j){return [r,j];});}).then(function(x){if(x[0].ok){location.replace('./');}else{m.textContent=x[1].error||'That didn’t work.';go.disabled=false;}})
.catch(function(){m.textContent='No connection. Try again.';go.disabled=false;});};})();
</script></body></html>"""
