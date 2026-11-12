"""The dashboard: http://localhost:8789 (or the next free port) on the Mac running the bot.

Every judged listing with its photo, price, why the bot rated it so, and
Claude's verdict; star, hide, or ask Claude about any of them. Served by the
running bot (`flipperbot run` starts it), stdlib only.

Listing text comes from strangers: the page builds everything with
textContent, never innerHTML, so a title can't inject markup. Actions are POSTs
that need an `X-Flipperbot` header, which other websites can't send to this
server (no CORS), and the Host header is checked, so a web page you visit can't
star, hide or spend Claude checks behind your back.
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.request
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from . import ai, niches, notify
from .config import Settings
from .db import DB, TIER_RANK

LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "::1"}
# Claude checks you asked for, in the order you asked: one at a time, first in the list is running.
_queue: list[str] = []
_cv = threading.Condition()
_worker: threading.Thread | None = None


def _url_file() -> Path:
    from . import config

    return config.HOME / "dashboard.url"


def url(s: Settings) -> str:
    """Where the running bot serves the dashboard. Its port moves on if the usual one
    is taken by another app, so the bot writes down the one it got."""
    try:
        return _url_file().read_text().strip()
    except OSError:
        return f"http://localhost:{s.dashboard_port}"


def is_flipperbot(u: str) -> bool:
    """Is flipperbot's dashboard answering at `u` (and not some other app on that port)?"""
    try:
        with urllib.request.urlopen(u + "/api/stats", timeout=2) as r:
            return "priced_models" in json.loads(r.read())
    except Exception:
        return False


def _small_photo(u: str) -> str:
    return re.sub(r";s=\d+x\d+", ";s=400x400", u)


def listing_json(r: Any) -> dict[str, Any]:
    photos = json.loads(r["photos"] or "[]")
    a = json.loads(r["ai"]) if r["ai"] else None
    if ai.is_limit_error(a):  # an older check that only hit the usage limit: not really checked
        a = None
    return {
        "key": r["key"], "source": r["source"], "niche": r["niche"] or "watches",
        "icon": niches.get(r["niche"]).icon, "url": r["url"], "title": r["title"], "price": r["price_ron"],
        "negotiable": bool(r["negotiable"]), "city": r["city"], "tier": r["tier"], "reason": r["reason"],
        "value": r["est_value_ron"], "profit": r["profit_ron"], "model": r["model_key"],
        "flags": json.loads(r["flags"] or "[]"), "delivery": bool(r["delivery"]),
        "photo": _small_photo(photos[0]) if photos else None, "photos": len(photos),
        "first_seen": r["first_seen"], "last_seen": r["last_seen"],
        "starred": bool(r["starred"]), "hidden": bool(r["hidden"]), "ai": a, "triage": r["triage"],
        "ai_running": bool(_queue) and _queue[0] == r["key"],
        "ai_queued": _queue.index(r["key"]) if r["key"] in _queue[1:] else None,  # how many ahead
    }


# What the bot finds interesting and you haven't decided on yet: deals, lots, old watches whose model
# isn't clear, sellers who don't know what they have. Only recently seen ones (still for sale).
INTERESTING = """triage IS NULL AND hidden = 0 AND last_seen >= datetime('now', '-3 days') AND (
    tier IN ('real_good', 'good')
    OR (tier = 'mid' AND (flags LIKE '%"lot"%' OR flags LIKE '%"naive"%' OR reason LIKE '%Claude will look%')))"""

VIEWS = {
    "interesting": (INTERESTING, "rank"),
    "deals": ("tier IN ('real_good','good') AND hidden=0", "rank"),
    "maybe": ("tier = 'mid' AND hidden=0", "rank"),
    "suspect": ("tier = 'suspect' AND hidden=0", "new"),
    "starred": ("starred=1", "rank"),
    "checked": ("ai IS NOT NULL", "ai"),
    "new": ("tier IN ('real_good','good','mid','suspect') AND hidden=0", "new"),
    "hidden": ("hidden=1", "new"),
}
ORDER = {
    "rank": "CASE tier WHEN 'real_good' THEN 4 WHEN 'good' THEN 3 WHEN 'mid' THEN 2 WHEN 'suspect' THEN 1 ELSE 0 END DESC, COALESCE(profit_ron,0) DESC, last_seen DESC",
    "new": "first_seen DESC",
    "ai": "ai_at DESC",
    "cheap": "price_ron ASC",
}


def query(db: DB, view: str, q: str = "", sort: str = "", limit: int = 120, niche: str = "") -> list[dict[str, Any]]:
    where, default_sort = VIEWS.get(view, VIEWS["deals"])
    args: list[Any] = []
    if niche in niches.ALL:
        where = f"({where}) AND niche = ?"
        args.append(niche)
    if q:
        where += " AND (title LIKE ? OR model_key LIKE ? OR city LIKE ?)"
        args += [f"%{q}%"] * 3
    order = ORDER.get(sort or default_sort, ORDER["rank"])
    rows = db.conn.execute(f"SELECT * FROM listings WHERE {where} ORDER BY {order} LIMIT ?", [*args, limit]).fetchall()
    return [listing_json(r) for r in rows]


def stats(db: DB, s: Settings, niche: str = "") -> dict[str, Any]:
    c = db.conn
    nf, na = ("AND niche = ?", [niche]) if niche in niches.ALL else ("", [])
    counts = {r["tier"]: r["n"] for r in c.execute(f"SELECT tier, COUNT(*) n FROM listings WHERE hidden=0 {nf} GROUP BY tier", na)}
    return {
        "total": c.execute(f"SELECT COUNT(*) FROM listings WHERE 1=1 {nf}", na).fetchone()[0],
        "counts": {t: counts.get(t, 0) for t in TIER_RANK},
        "starred": c.execute(f"SELECT COUNT(*) FROM listings WHERE starred=1 {nf}", na).fetchone()[0],
        "interesting": c.execute(f"SELECT COUNT(*) FROM listings WHERE {INTERESTING} {nf}", na).fetchone()[0],
        "niches": [{"key": k, "label": niches.get(k).label, "icon": niches.get(k).icon} for k in s.niches],
        "priced_models": c.execute(
            "SELECT COUNT(*) FROM (SELECT model_key FROM listings WHERE model_key LIKE '%|%' GROUP BY model_key HAVING COUNT(*) >= ?)",
            (s.min_comps,),
        ).fetchone()[0],
        "last_poll": db.kv_get("last_poll"),
        "ai_used": ai.used_today(db), "ai_limit": s.ai_daily_limit, "ai_available": ai.available(s),
        "ai_paused_until": time.strftime("%H:%M", time.localtime(_paused_until)) if _paused_until > time.time() else None,
        "ai_queue": len(_queue),
        "telegram": notify.enabled(s),
        "facebook": {k: v for k, v in (db.kv_get("facebook") or {}).items() if k in ("state", "at", "listings")},
        "today": date.today().isoformat(),
    }


def _check(s: Settings, key: str) -> None:
    """One Claude check you asked for. Its notes land on the dashboard; if Claude values it as a
    real good deal and is sure enough, it also goes to Telegram (so the verdict reaches your phone)."""
    from . import bot

    db = DB(s.db_path)
    row = db.get(key)
    if not row:
        return
    s.ai_daily_limit = max(s.ai_daily_limit, ai.used_today(db) + 1)  # you asked: it runs
    result = ai.check(db, row, s)
    if not result:
        return
    bot.claude_value(db, row, result, s)
    row = db.get(key)
    ok, _ = bot.confirmed(result, s, row["segment"])
    if ok and row["tier"] == "real_good":  # you sent it: the verdict goes to your phone too
        notify.send(s, notify.deal_text(row, result), (json.loads(row["photos"] or "[]") or [None])[0])
        db.mark_notified(key, "real_good")


_paused_until = 0.0  # Claude's plan limit: the queue waits until then


def _work(s: Settings) -> None:
    global _paused_until
    while True:
        with _cv:
            while not _queue:
                _cv.wait()
            key = _queue[0]
        wait = _paused_until - time.time()
        if wait > 0:  # the limit resets at _paused_until; your requests stay queued meanwhile
            time.sleep(min(wait, 60))
            continue
        done = True
        try:
            _check(s, key)
        except ai.UsageLimit as e:
            _paused_until = e.until
            done = False  # same listing again once the limit resets
            print(f"Claude's usage limit reached; queue paused until {time.strftime('%H:%M', time.localtime(e.until))}")
        except Exception as e:  # one failed check mustn't stop the queue
            print(f"Claude check failed for {key}: {e!r}")
        finally:
            if done:
                with _cv:
                    _queue.pop(0)


def send_to_claude(s: Settings, key: str) -> None:
    global _worker
    with _cv:
        if key not in _queue:
            _queue.append(key)
            _cv.notify()
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_work, args=(s,), daemon=True)
            _worker.start()


def make_handler(s: Settings) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: Any) -> None:  # keep the bot's log readable
            pass

        def _host_ok(self) -> bool:
            if s.dashboard_lan:
                return True
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in LOCAL_HOSTS

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")  # OLX photos load without telling OLX where from
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj: Any, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

        def do_GET(self) -> None:
            if not self._host_ok():
                return self._send(403, b"forbidden", "text/plain")
            u = urlparse(self.path)
            qs = {k: v[0] for k, v in parse_qs(u.query).items()}
            db = DB(s.db_path)
            if u.path == "/":
                self._send(200, PAGE.encode(), "text/html; charset=utf-8")
            elif u.path == "/api/listings":
                self._json(query(db, qs.get("view", "deals"), qs.get("q", ""), qs.get("sort", ""), niche=qs.get("niche", "")))
            elif u.path == "/api/listing":
                row = db.get(qs.get("key", ""))
                self._json(listing_json(row) if row else {"error": "unknown listing"}, 200 if row else 404)
            elif u.path == "/api/stats":
                self._json(stats(db, s, qs.get("niche", "")))
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:
            if not self._host_ok() or self.headers.get("X-Flipperbot") != "1":
                return self._send(403, b"forbidden", "text/plain")
            # Browsers send the listing key URL-encoded ("olx%3A123"): decode before matching.
            m = re.fullmatch(r"/api/(star|unstar|hide|unhide|ai|skip|fake)/([\w:.-]+)", unquote(urlparse(self.path).path))
            if not m:
                return self._send(404, b"not found", "text/plain")
            action, key = m.groups()
            db = DB(s.db_path)
            if not db.get(key):
                return self._json({"error": "unknown listing"}, 404)
            if action in ("star", "unstar"):
                db.set_flag(key, "starred", action == "star")
            elif action in ("hide", "unhide"):
                db.set_flag(key, "hidden", action == "hide")
                if action == "unhide":
                    db.set_triage(key, None)  # back in Interesting if it still is
            elif action == "skip":  # not worth a Claude check: out of Interesting, still in Deals/Maybe
                db.set_triage(key, "skip")
            elif action == "fake":  # fake or not interested: out of sight (the Hidden tab has it)
                db.set_triage(key, "fake")
                db.set_flag(key, "hidden", True)
            else:
                if not ai.available(s):
                    return self._json({"error": "Claude Code isn't installed on this Mac (see README)."}, 400)
                db.set_triage(key, "claude")
                send_to_claude(s, key)
            self._json(listing_json(db.get(key)))

    return Handler


def serve(s: Settings, background: bool = False) -> ThreadingHTTPServer | None:
    host = "0.0.0.0" if s.dashboard_lan else "127.0.0.1"
    server = None
    for port in range(s.dashboard_port, s.dashboard_port + 30):  # another app may hold the usual port
        try:
            server = ThreadingHTTPServer((host, port), make_handler(s))
            break
        except OSError:
            continue
    if server is None:
        print(f"dashboard: no free port between {s.dashboard_port} and {s.dashboard_port + 29}")
        return None
    address = f"http://localhost:{server.server_address[1]}"
    _url_file().parent.mkdir(parents=True, exist_ok=True)
    _url_file().write_text(address)
    print(f"dashboard: {address}")
    if background:
        threading.Thread(target=server.serve_forever, daemon=True).start()
    else:
        server.serve_forever()
    return server


PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>flipperbot</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⌚</text></svg>">
<style>
:root {
  --bg: #f6f5f2; --card: #fff; --ink: #1d1d1b; --muted: #6f6c66; --line: #e4e1da;
  --accent: #1d1d1b;
  --rg: #0f7b4a; --rg-bg: #dff3e8; --g: #3a7d1f; --g-bg: #ecf5e2; --mid: #8a6100; --mid-bg: #fbf0d6;
  --sus: #a3321f; --sus-bg: #fbe4df; --bad: #77736c; --bad-bg: #eeece8;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #141413; --card: #1e1e1c; --ink: #f0eee9; --muted: #9b978f; --line: #2f2e2b; --accent: #f0eee9;
    --rg: #6fd6a0; --rg-bg: #133826; --g: #a5d67f; --g-bg: #23331a; --mid: #f0c25e; --mid-bg: #3a2e12;
    --sus: #f09582; --sus-bg: #3d1d17; --bad: #a7a39c; --bad-bg: #2a2927;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
header { position: sticky; top: 0; z-index: 2; background: var(--bg); border-bottom: 1px solid var(--line); }
.bar { max-width: 1200px; margin: 0 auto; padding: 14px 20px 0; }
.top { display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; }
h1 { font-size: 20px; margin: 0; letter-spacing: -0.01em; }
.status { color: var(--muted); font-size: 13px; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; background: var(--bad); }
.dot.on { background: var(--rg); }
nav { display: flex; gap: 4px; margin-top: 12px; overflow-x: auto; }
nav button { border: 0; background: none; color: var(--muted); font: inherit; padding: 8px 12px 10px; cursor: pointer; border-bottom: 2px solid transparent; white-space: nowrap; }
nav button.on { color: var(--ink); border-color: var(--accent); font-weight: 600; }
nav .n { font-size: 12px; margin-left: 4px; opacity: .8; }
.tools { display: flex; gap: 8px; padding: 10px 0 12px; }
input[type=search], select { font: inherit; padding: 7px 10px; border: 1px solid var(--line); border-radius: 8px; background: var(--card); color: var(--ink); }
input[type=search] { flex: 1; min-width: 0; }
main { max-width: 1200px; margin: 0 auto; padding: 18px 20px 60px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(270px, 1fr)); gap: 16px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }
.ph { aspect-ratio: 4 / 3; background: var(--bad-bg); display: grid; place-items: center; font-size: 40px; color: var(--muted); overflow: hidden; }
.ph img { width: 100%; height: 100%; object-fit: cover; display: block; }
.body { padding: 12px 14px 14px; display: flex; flex-direction: column; gap: 6px; flex: 1; }
.row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.pill { font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; padding: 3px 8px; border-radius: 999px; }
.t-real_good { color: var(--rg); background: var(--rg-bg); } .t-good { color: var(--g); background: var(--g-bg); }
.t-mid { color: var(--mid); background: var(--mid-bg); } .t-suspect { color: var(--sus); background: var(--sus-bg); }
.t-bad { color: var(--bad); background: var(--bad-bg); }
.title { font-weight: 600; color: var(--ink); text-decoration: none; }
.title:hover { text-decoration: underline; }
.reason { color: var(--muted); font-size: 13px; }
.prices { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.prices > div { padding: 8px 10px; }
.prices > div + div { border-left: 1px solid var(--line); }
.prices .k { font-size: 11px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--muted); }
.prices .n { font-size: 18px; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1.25; white-space: nowrap; letter-spacing: -0.01em; }
.prices .n.range { font-size: 15px; padding-top: 2px; }
.prices .n.na { font-size: 14px; font-weight: 500; color: var(--muted); padding-top: 4px; }
.prices .src { font-size: 11px; color: var(--muted); }
.profit { grid-column: 1 / -1; border-top: 1px solid var(--line); font-size: 13px; font-variant-numeric: tabular-nums; }
.profit b { color: var(--rg); } .profit b.neg { color: var(--sus); }
.ai { border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; font-size: 13px; display: flex; flex-direction: column; gap: 4px; }
.ai .v { font-weight: 700; }
.ai .lot { display: flex; flex-direction: column; gap: 2px; }
.v-buy { color: var(--rg); } .v-negotiate { color: var(--mid); } .v-skip { color: var(--sus); }
.meta { color: var(--muted); font-size: 12px; margin-top: auto; padding-top: 4px; }
.actions { display: flex; gap: 6px; flex-wrap: wrap; }
.actions a, .actions button { font: inherit; font-size: 13px; padding: 6px 10px; border-radius: 8px; border: 1px solid var(--line); background: none; color: var(--ink); cursor: pointer; text-decoration: none; }
.actions a.primary { background: var(--accent); color: var(--bg); border-color: var(--accent); }
.actions button:disabled { opacity: .5; cursor: default; }
.actions button.claude { border-color: var(--g); color: var(--g); font-weight: 600; }
.triage { display: grid; grid-template-columns: auto 1fr; gap: 6px; }
.triage button, .triage a { font: inherit; font-size: 13px; padding: 8px 10px; border-radius: 8px; border: 1px solid var(--line);
  background: none; color: var(--ink); cursor: pointer; text-decoration: none; text-align: center; white-space: nowrap; }
.triage .t-claude { grid-column: 1 / -1; background: var(--accent); color: var(--bg); border-color: var(--accent); font-weight: 600; }
.triage .t-fake { color: var(--sus); border-color: var(--sus-bg); }
.card.leaving { opacity: 0; transform: scale(.97); transition: opacity .18s, transform .18s; }
.hint { color: var(--muted); font-size: 12px; margin: -6px 0 12px; }
.empty { color: var(--muted); text-align: center; padding: 60px 20px; }
.err { color: var(--sus); font-size: 13px; }
</style>
</head>
<body>
<header><div class="bar">
  <div class="top"><h1>⌚ flipperbot</h1><span class="status" id="status">loading…</span></div>
  <nav id="tabs"></nav>
  <div class="tools">
    <input type="search" id="q" placeholder="Search title, model, city…">
    <select id="sort" aria-label="Sort">
      <option value="">Best first</option><option value="new">Newest</option><option value="cheap">Cheapest</option>
    </select>
  </div>
</div></header>
<main><div class="hint" id="hint" hidden>Keys: <b>C</b> let Claude check · <b>S</b> skip · <b>F</b> fake / not interested (top card)</div><div class="grid" id="grid"></div><div class="empty" id="empty" hidden></div></main>
<script>
const TABS = [
  ["interesting", "Interesting", s => s.interesting],
  ["deals", "Deals", s => s.counts.real_good + s.counts.good],
  ["maybe", "Maybe", s => s.counts.mid],
  ["suspect", "Likely fake", s => s.counts.suspect],
  ["starred", "Starred", s => s.starred],
  ["checked", "Claude checked", null],
  ["new", "Newest", null],
  ["hidden", "Hidden", null],
];
const LABEL = { real_good: "real good", good: "good", mid: "maybe", suspect: "likely fake", bad: "bad" };
const EMPTY = {
  interesting: "Nothing new to look at. The bot checks OLX every 5–10 minutes; interesting finds land here.",
  deals: "No deals yet. The bot checks OLX every 5–10 minutes; good finds land here and on Telegram.",
  maybe: "Nothing to look at twice yet.", suspect: "No likely fakes.", starred: "Star a listing to keep it here.",
  checked: "Nothing checked by Claude yet. Press “Send to Claude” on any listing.", new: "Nothing yet.", hidden: "Nothing hidden.",
};
let view = location.hash.slice(1) || "interesting", stats = null;


function h(tag, attrs = {}, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") el.className = v; else if (k.startsWith("on")) el.addEventListener(k.slice(2), v); else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return el;
}
const lei = n => n == null ? "?" : n.toLocaleString("ro-RO") + " lei";
function ago(iso) {
  if (!iso) return "";
  const m = Math.round((Date.now() - new Date(iso)) / 60000);
  if (m < 2) return "just now"; if (m < 60) return m + " min ago";
  const hrs = Math.round(m / 60); if (hrs < 48) return hrs + " h ago";
  return Math.round(hrs / 24) + " days ago";
}
async function api(path, opts) {
  const r = await fetch(path, opts);
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
const act = (action, key) => api(`/api/${action}/${encodeURIComponent(key)}`, { method: "POST", headers: { "X-Flipperbot": "1" } });

function aiBox(a, l) {
  if (a.error) return h("div", { class: "ai" }, h("span", { class: "err" }, "Claude couldn't check it: " + String(a.error).slice(0, 160)));
  const isLot = (l.flags || []).includes("lot");
  const ws = (a.items || a.watches || []).slice().sort((x, y) => (y.notable === true) - (x.notable === true) || (y.value_ron || 0) - (x.value_ron || 0));
  const label = w => [w.brand, w.model, w.reference].filter(Boolean).join(" ") || "unidentified";
  const names = isLot
    ? h("div", { class: "lot" }, ws.slice(0, 8).map(w => h("div", {}, (w.notable ? "⭐ " : "• ") + label(w),
        w.value_ron ? ` ~${lei(w.value_ron)}` : "", w.photo ? h("span", { class: "reason" }, ` (photo ${w.photo})`) : null)),
        ws.length > 8 ? h("div", { class: "reason" }, `+${ws.length - 8} more`) : null)
    : ws.map(label).join("; ");
  const v = (a.verdict || "?").toLowerCase();
  return h("div", { class: "ai" },
    h("div", {}, "🤖 ", h("span", { class: "v v-" + v }, v.toUpperCase()),
      typeof a.confidence === "number" ? ` · ${a.confidence}% sure` : "", a.offer_ron ? ` · offer ${lei(a.offer_ron)}` : ""),
    names && h("div", {}, names),
    h("div", {}, `authenticity: ${a.authenticity || "?"} · resale ${lei(a.resale_ron_low)}–${lei(a.resale_ron_high)}` + (a.repair_cost_ron ? ` · repair ~${lei(a.repair_cost_ron)}` : "")),
    a.summary && h("div", { class: "reason" }, a.summary),
    (a.questions_for_seller || []).length ? h("div", { class: "reason" }, "Ask the seller: " + a.questions_for_seller.slice(0, 3).join(" · ")) : null);
}

// Asking price next to what it's worth: the bot's market estimate, else Claude's resale range.
function priceBox(l) {
  const a = l.ai && !l.ai.error ? l.ai : null;
  let worth, src, profit = l.profit;
  if (l.value) {
    worth = "~" + lei(l.value); src = "from similar listings";
  } else if (a && a.resale_ron_high) {
    worth = a.resale_ron_low && a.resale_ron_low !== a.resale_ron_high
      ? `${a.resale_ron_low.toLocaleString("ro-RO")}–${lei(a.resale_ron_high)}` : "~" + lei(a.resale_ron_high);
    src = "Claude's estimate";
    const mid = ((a.resale_ron_low || a.resale_ron_high) + a.resale_ron_high) / 2;
    profit = Math.round(mid - l.price - (a.repair_cost_ron || 0));
  }
  return h("div", { class: "prices" },
    h("div", {}, h("div", { class: "k" }, "Price"), h("div", { class: "n" }, lei(l.price)),
      h("div", { class: "src" }, l.negotiable ? "negotiable" : "asking")),
    h("div", {}, h("div", { class: "k" }, "Est. value"),
      worth ? h("div", { class: "n" + (worth.includes("–") ? " range" : "") }, worth) : h("div", { class: "n na" }, "not enough data yet"),
      worth ? h("div", { class: "src" }, src) : null),
    profit != null && worth ? h("div", { class: "profit" }, "profit ",
      h("b", { class: profit < 0 ? "neg" : "" }, (profit < 0 ? "−" : "~") + lei(Math.abs(profit))),
      l.value && a && a.resale_ron_high ? ` · Claude says ${lei(a.resale_ron_low)}–${lei(a.resale_ron_high)}` : "") : null);
}

// The Interesting tab: decide, and the card leaves the list. Keys C / S / F act on the top card.
async function decide(l, el, action) {
  el.classList.add("leaving");
  try { await act(action, l.key); } catch (err) { el.classList.remove("leaving"); alert(err.message); return; }
  setTimeout(() => { el.remove(); if (!document.querySelector("#grid article")) load(); }, 180);
  refreshStats();
}

function triageActions(l, el) {
  return h("div", { class: "triage" },
    h("button", { class: "t-claude", title: "C", onclick: () => decide(l, el, "ai") }, "🤖 Let Claude check"),
    h("button", { class: "t-skip", title: "S", onclick: () => decide(l, el, "skip") }, "Skip"),
    h("button", { class: "t-fake", title: "F", onclick: () => decide(l, el, "fake") }, "Fake / not interested"));
}

document.addEventListener("keydown", e => {
  if (view !== "interesting" || e.target.matches("input, select, textarea") || e.metaKey || e.ctrlKey) return;
  const action = { c: "ai", s: "skip", f: "fake" }[e.key.toLowerCase()];
  const first = document.querySelector("#grid article:not(.leaving)");
  if (action && first && first.listing) decide(first.listing, first, action);
});

function card(l) {
  const el = h("article", { class: "card" });
  const draw = () => {
    const img = l.photo ? h("img", { src: l.photo, alt: "", loading: "lazy", referrerpolicy: "no-referrer", onerror: e => e.target.replaceWith("⌚") }) : "⌚";
    const waiting = l.ai_running || l.ai_queued != null;
    const aiLabel = l.ai_running && stats && stats.ai_paused_until ? `Waiting for Claude (limit resets ~${stats.ai_paused_until})`
      : l.ai_running ? "Claude is looking…" : l.ai_queued != null ? `In Claude's queue (${l.ai_queued} ahead)`
      : l.ai ? "🤖 Send to Claude again" : "🤖 Send to Claude";
    const aiBtn = h("button", { class: l.ai ? "" : "claude", disabled: waiting, onclick: async e => {
      e.target.disabled = true; e.target.textContent = "Sending…";
      try { Object.assign(l, await act("ai", l.key)); draw(); poll(l, el); } catch (err) { e.target.textContent = err.message; }
    } }, aiLabel);
    if (waiting && !el.polling) poll(l, el);
    el.replaceChildren(
      h("a", { class: "ph", href: l.url, target: "_blank", rel: "noopener noreferrer" }, img),
      h("div", { class: "body" },
        h("div", { class: "row" }, h("span", { class: "pill t-" + l.tier }, LABEL[l.tier] || l.tier)),
        priceBox(l),
        h("a", { class: "title", href: l.url, target: "_blank", rel: "noopener noreferrer" }, l.title),
        h("div", { class: "reason" }, l.reason || ""),
        l.ai ? aiBox(l.ai, l) : null,
        h("div", { class: "meta" }, [l.source === "facebook" ? "Facebook" : "OLX", l.city, l.negotiable ? "negotiable" : "", l.delivery ? "OLX delivery" : "", "found " + ago(l.first_seen)].filter(Boolean).join(" · ")),
        view === "interesting" ? triageActions(l, el) : h("div", { class: "actions" },
          h("a", { class: "primary", href: l.url, target: "_blank", rel: "noopener noreferrer" }, l.source === "facebook" ? "Open on Facebook ↗" : "Open on OLX ↗"),
          h("button", { onclick: async () => { Object.assign(l, await act(l.starred ? "unstar" : "star", l.key)); draw(); refreshStats(); } }, l.starred ? "★ Starred" : "☆ Star"),
          h("button", { onclick: async () => { await act(l.hidden ? "unhide" : "hide", l.key); el.remove(); refreshStats(); } }, l.hidden ? "Unhide" : "Hide"),
          aiBtn)));
  };
  draw(); el.redraw = draw; el.listing = l;
  return el;
}

function poll(l, el) {
  if (el.polling) return;
  el.polling = setInterval(async () => {
    let got; try { got = await api(`/api/listing?key=${encodeURIComponent(l.key)}`); } catch { return; }
    const before = l.ai_running || l.ai_queued != null;
    Object.assign(l, got); el.redraw();
    if (!(got.ai_running || got.ai_queued != null)) { clearInterval(el.polling); el.polling = null; if (before) refreshStats(); }
  }, 6000);
}

function drawTabs() {
  document.getElementById("tabs").replaceChildren(...TABS.map(([id, name, count]) =>
    h("button", { class: id === view ? "on" : "", onclick: () => { view = id; location.hash = id; drawTabs(); load(); } },
      name, stats && count ? h("span", { class: "n" }, count(stats)) : null)));
}

async function refreshStats() {
  try { stats = await api("/api/stats"); } catch { return; }
  const p = stats.last_poll, fresh = p && (Date.now() - new Date(p.at)) < 20 * 60000;
  document.getElementById("status").replaceChildren(
    h("span", { class: "dot" + (fresh ? " on" : "") }),
    p ? `${fresh ? "running" : "not running"} · last check ${ago(p.at)}` : "waiting for the first check",
    ` · ${stats.total.toLocaleString("ro-RO")} listings tracked · ${stats.priced_models} models priced`,
    !stats.ai_available ? " · Claude not installed"
      : stats.ai_paused_until ? ` · Claude hit your plan's usage limit: ${stats.ai_queue} waiting, resumes ~${stats.ai_paused_until}`
      : ` · Claude ${stats.ai_used} checks today` + (stats.ai_queue ? `, ${stats.ai_queue} in queue` : ""),
    stats.telegram ? "" : " · Telegram not set up",
    !stats.facebook.state ? " · Facebook not set up" :
      stats.facebook.state === "logged_out" ? " · Facebook logged out: run flipperbot facebook-login" :
      stats.facebook.state === "error" ? " · Facebook: last run failed, retrying" :
      stats.facebook.at ? ` · Facebook checked ${ago(stats.facebook.at)}` : " · Facebook on");
  drawTabs();
}

let loading = 0;
async function load() {
  const mine = ++loading;
  const q = document.getElementById("q").value.trim(), sort = document.getElementById("sort").value;
  const rows = await api(`/api/listings?view=${view}&q=${encodeURIComponent(q)}&sort=${sort}`);
  if (mine !== loading) return;
  document.getElementById("grid").replaceChildren(...rows.map(card));
  document.getElementById("hint").hidden = view !== "interesting" || !rows.length;
  const empty = document.getElementById("empty");
  empty.hidden = rows.length > 0; empty.textContent = q ? "Nothing matches." : EMPTY[view];
}

let t;
document.getElementById("q").addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 250); });
document.getElementById("sort").addEventListener("change", load);
window.addEventListener("hashchange", () => { view = location.hash.slice(1) || "interesting"; drawTabs(); load(); });
drawTabs(); refreshStats(); load();
setInterval(refreshStats, 60000);
setInterval(() => { if (!document.hidden && !document.getElementById("q").value) load(); }, 120000);
</script>
</body>
</html>
"""
