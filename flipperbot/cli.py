"""flipperbot <command>

  app              what the Flipperbot app runs: start the bot if it isn't running, open the dashboard
  make-app         (Mac) put the one-click Flipperbot app in Applications
  open             open the dashboard in your browser (usually http://localhost:8789)
  setup            first-time setup: Telegram (guided) and a check that Claude Code is there
  run              poll forever (every 5-10 min), alert, AI-check, daily summary at 20:00
  poll             one poll, then exit
  backfill         read many pages for every search term once, to build the price book (no alerts)
  rescore          judge every stored listing again (after backfill or after changing settings)
  show             list stored listings by tier
  digest           send the daily summary now
  ai <url|key>     run the Claude check on one stored listing now
  telegram-setup   find your Telegram chat id after you've messaged your bot
  stats            what's in the database
  ebay-setup       add your free eBay developer keys, so estimates also use eBay listings
  claude-test      check that the bot can use Claude on this Mac (one tiny call, the way checks run)
  facebook-login   set up Facebook Marketplace: log in once with your SECOND account
  facebook-poll    one Facebook search run now (to test it), then exit
  start / stop     (Mac) run in the background from login on / stop that
  log              (Mac) follow what the background bot is doing
"""

from __future__ import annotations

import argparse
import json
import sys
import threading

from . import ai, autostart, bot, config, niches, notify, seed, web
from .db import DB, TIER_RANK
from .sources import olx


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="flipperbot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    sub.add_parser("run")
    sub.add_parser("poll")
    b = sub.add_parser("backfill")
    b.add_argument("--pages", type=int, default=5)
    sub.add_parser("rescore")
    sh = sub.add_parser("show")
    sh.add_argument("--tier", default="real_good,good,mid,suspect")
    sh.add_argument("-n", type=int, default=30)
    sub.add_parser("digest")
    a = sub.add_parser("ai")
    a.add_argument("target")
    sub.add_parser("telegram-setup")
    sub.add_parser("stats")
    sub.add_parser("app")
    sub.add_parser("make-app")
    sub.add_parser("open")
    sub.add_parser("dashboard")  # serve the dashboard only, without polling
    sub.add_parser("ebay-setup")
    sub.add_parser("claude-test")
    sub.add_parser("facebook-login")
    sub.add_parser("facebook-poll")
    sub.add_parser("start")
    sub.add_parser("stop")
    sub.add_parser("log")
    sub.add_parser("export-seed")  # maintainers: write the starter price book from this database
    args = p.parse_args(argv)

    s = config.load()
    db = DB(s.db_path)
    n = seed.load_if_empty(db)
    if n:
        print(f"Loaded the starter price book: {n} listings already priced.")

    if args.cmd == "setup":
        _setup(s)

    elif args.cmd == "app":
        import subprocess
        import time

        if sys.platform == "darwin" and not autostart.running():
            autostart.enable()
        for _ in range(40):  # the bot needs a few seconds to put its dashboard up
            if web.is_flipperbot(web.url(s)):
                break
            time.sleep(1)
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", web.url(s)], capture_output=True)

    elif args.cmd == "make-app":
        from . import macapp

        print(f"Made {macapp.make()}: click it to start flipperbot and open the dashboard. Drag it to the Dock to keep it there.")

    elif args.cmd in ("open", "dashboard"):
        import subprocess

        server = None
        if not web.is_flipperbot(web.url(s)):
            print("The bot isn't running, so the dashboard is served from here until you press Ctrl + C.")
            server = web.serve(s, background=True)
        if args.cmd == "open":
            subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", web.url(s)], capture_output=True)
            print(f"Opened {web.url(s)}")
        if server:
            try:
                threading.Event().wait()
            except KeyboardInterrupt:
                pass

    elif args.cmd == "ebay-setup":
        from .sources import ebay

        print("eBay prices come through eBay's official API. The keys are free:")
        print("1. Go to https://developer.ebay.com and sign up (any eBay account works).")
        print("2. Open 'Application Keysets' (from your name, top right), and create a PRODUCTION keyset.")
        print("   (If it asks about marketplace account deletion notifications, choose to opt out: the bot")
        print("    stores no eBay user data.)")
        print("3. Copy the 'App ID (Client ID)' and the 'Cert ID (Client Secret)'.\n")
        s.ebay_client_id = input("App ID (Client ID): ").strip()
        s.ebay_client_secret = input("Cert ID (Client Secret): ").strip()
        try:
            got = ebay._search_api(db, s, "seiko skx007")
        except Exception as e:
            sys.exit(f"eBay didn't accept those keys ({str(e)[:150]}). Check them and run: flipperbot ebay-setup")
        config.set_value("ebay_client_id", s.ebay_client_id)
        config.set_value("ebay_client_secret", s.ebay_client_secret)
        print(f"✓ eBay works ({len(got)} listings for a test search). Estimates now use eBay when OLX can't price a model.")
        if autostart.running():
            import os
            import subprocess

            subprocess.run(["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{autostart.LABEL}"], capture_output=True)

    elif args.cmd == "claude-test":
        import subprocess
        import tempfile

        if not ai.available(s):
            sys.exit("Claude Code isn't installed (or `claude` isn't on PATH). Install it: curl -fsSL https://claude.ai/install.sh | bash")
        with tempfile.TemporaryDirectory() as d:
            proc = subprocess.run(ai.CLAUDE_ARGS(s.claude_bin, s.ai_model), input='Reply with exactly: {"ok": true}',
                                  cwd=d, capture_output=True, text=True, timeout=180)
        try:
            w = json.loads(proc.stdout)
        except json.JSONDecodeError:
            w = {}
        said = str(w.get("result") or proc.stderr or proc.stdout or "no output").strip()[:400]
        if proc.returncode == 0 and not w.get("is_error") and '"ok"' in said:
            print(f"✓ Claude works for the bot (model: {', '.join(w.get('modelUsage') or {}) or s.ai_model}).")
            print("Real good deals will be checked by themselves, and 'Send to Claude' works.")
        else:
            until = ai.limit_reset(said)
            print("✗ Claude didn't work for the bot. It said:\n  " + said)
            if until:
                import time

                print(f"That's your plan's usage limit; it resets around {time.strftime('%H:%M', time.localtime(until))}.")
            elif "login" in said.lower() or "auth" in said.lower() or "api key" in said.lower():
                print("Log in once: type  claude  in Terminal, log in, then /exit. Then run this again.")
            sys.exit(1)

    elif args.cmd == "facebook-login":
        from .sources import facebook

        if not facebook.installed():
            sys.exit("Facebook support isn't installed. Paste the install command again, then retry.")
        import subprocess

        if not facebook.channel():
            print("Google Chrome isn't installed, so getting a Chromium browser (once, ~150 MB).")
            print("(Installing Google Chrome from google.com/chrome first gives a steadier window.)")
            subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        try:
            facebook.login()
        except facebook.NotLoggedIn as e:
            sys.exit(str(e))
        except Exception as e:
            sys.exit(f"The browser stopped ({type(e).__name__}: {str(e)[:200]}). Run `flipperbot facebook-login` again.")
        db.kv_set("facebook", {"state": "ok", "next_at": 0})
        if autostart.running():
            subprocess.run(["launchctl", "kickstart", "-k", f"gui/{__import__('os').getuid()}/{autostart.LABEL}"], capture_output=True)
        print("The bot will now also check Facebook every 30-60 minutes.")

    elif args.cmd == "facebook-poll":
        from .sources import facebook

        if not facebook.installed():
            sys.exit("Facebook support isn't installed. Paste the install command again, then retry.")
        state = db.kv_get("facebook", {})
        db.kv_set("facebook", {**state, "state": state.get("state") or "ok"})
        n = bot.poll_facebook(db, s)
        print(f"facebook: {n} listings. State: {db.kv_get('facebook', {}).get('state')}")
        for r in db.conn.execute("SELECT tier, price_ron, title FROM listings WHERE source='facebook' ORDER BY first_seen DESC LIMIT 15"):
            print(f"  {r['tier']:<9} {r['price_ron'] or '?':>6} lei  {r['title'][:70]}")

    elif args.cmd == "start":
        autostart.enable()

    elif args.cmd == "stop":
        autostart.disable()

    elif args.cmd == "log":
        import os

        os.execvp("tail", ["tail", "-n", "40", "-f", str(autostart.LOG)])

    elif args.cmd == "export-seed":
        print(f"wrote {seed.export(db)} listings to {seed.SEED}")

    elif args.cmd == "run":
        if not ai.available(s):
            print("note: `claude` not found on PATH; AI checks are off")
        if not notify.enabled(s):
            print("note: Telegram not set up; alerts print here instead")
        bot.run_forever(db, s)

    elif args.cmd == "poll":
        bot.poll(db, s)
        bot.deliver(db, s)

    elif args.cmd == "backfill":
        from . import niches

        jobs = [(t, None, k) for k in s.niches for t in (s.search_pool + s.focus_pool if k == "watches"
                                                          else list(niches.get(k).search_pool + niches.get(k).focus_pool))]
        for i, job in enumerate(jobs):
            term = job[0]
            print(f"[{i + 1}/{len(jobs)}] {niches.get(job[2]).icon} {term}")
            try:
                listings = bot.fetch_all([job], s, pages=args.pages)
            except olx.Blocked as e:
                sys.exit(f"{e}. Stopping; try again later.")
            bot.learn_categories(db, listings)
            bot.process(db, listings, s, alert=False)
            bot.time.sleep(bot.random.uniform(*s.pause_between_requests_s))
        print(f"\"ceas\" listings by OLX category: {db.kv_get('olx_ceas_categories', {})}")
        _rescore(db, s)

    elif args.cmd == "rescore":
        _rescore(db, s)

    elif args.cmd == "show":
        tiers = args.tier.split(",")
        for r in db.by_tier(tiers, limit=args.n):
            profit = f" profit~{r['profit_ron']}" if r["profit_ron"] else ""
            print(f"{r['tier']:<9} {r['price_ron']:>6} lei{profit:<14} {r['title'][:55]:<55} | {r['reason']}")
            print(f"{'':>9} {r['url']}")
            if r["ai"]:
                res = json.loads(r["ai"])
                print(f"{'':>9} AI: {res.get('verdict')} · {res.get('summary', res.get('error', ''))}")

    elif args.cmd == "digest":
        print(f"sent {bot.digest(db, s)} listings")

    elif args.cmd == "ai":
        row = db.get(args.target) or db.conn.execute("SELECT * FROM listings WHERE url LIKE ?", (args.target.split("?")[0] + "%",)).fetchone()
        if not row:
            sys.exit("not in the database: run a poll that finds it first, or pass its key (olx:<id>)")
        if not ai.available(s):
            sys.exit("`claude` isn't on PATH. Install Claude Code and log in first.")
        s.ai_daily_limit = max(s.ai_daily_limit, ai.used_today(db) + 1)  # a manual check always runs
        try:
            res = ai.check(db, row, s)
        except ai.UsageLimit as e:
            import time

            sys.exit(f"Claude's usage limit is reached; it resets around {time.strftime('%H:%M', time.localtime(e.until))}.")
        print(json.dumps(res, indent=2, ensure_ascii=False))

    elif args.cmd == "telegram-setup":
        if not s.telegram_token:
            sys.exit("Put telegram_token in ~/.flipperbot/config.toml first (from @BotFather).")
        updates = notify._call(s, "getUpdates").get("result", [])
        chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "") for u in updates if "message" in u}
        if not chats:
            sys.exit("No messages yet. Send your bot any message on Telegram, then run this again.")
        for cid, name in chats.items():
            print(f"chat id {cid} ({name}): put  telegram_chat_id = \"{cid}\"  in config.toml")

    elif args.cmd == "stats":
        c = db.conn
        print("listings:", c.execute("SELECT COUNT(*) FROM listings").fetchone()[0])
        for r in c.execute("SELECT tier, COUNT(*) n FROM listings GROUP BY tier ORDER BY n DESC"):
            print(f"  {r['tier']}: {r['n']}")
        print("models with 4+ listings (priced):", c.execute(
            "SELECT COUNT(*) FROM (SELECT model_key FROM listings WHERE model_key IS NOT NULL GROUP BY model_key HAVING COUNT(*) >= 4)"
        ).fetchone()[0])
        print("watch categories:", bot.watch_categories(db))
        print("AI checks today:", ai.used_today(db), "/", s.ai_daily_limit)


def _setup(s: config.Settings) -> None:
    import shutil
    import time

    cfg = config.HOME / "config.toml"
    print(f"Settings file: {cfg}\n")
    print("== Telegram: alerts on your phone ==")
    me = None
    if s.telegram_token:
        me, why = notify.check_token(s)
        if not me:
            print(f"The saved token didn't work: {why}\n")
    if not me:
        print("1. In Telegram, search for @BotFather and open it.")
        print("2. Send it:  /newbot")
        print("3. It asks for a name, then a username ending in 'bot' (e.g. arnold_flipper_bot).")
        print("4. It answers with a message containing a token: a long code like 123456789:AAH...")
        print("   Copy that message (all of it is fine) and paste it here.\n")
    tries = 0
    while not me:
        tries += 1
        pasted = input("Paste the token and press Enter: ")
        token = notify.find_token(pasted)
        if not token:
            print("  That doesn't look like a token. It's digits, a colon, then ~35 letters/digits,")
            print("  like 123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw. Try copying it again.\n")
        else:
            s.telegram_token = token
            me, why = notify.check_token(s)
            if not me:
                print(f"  {why}\n")
                if "reach" in why:
                    print("  This is a connection problem, not your token. Check the Mac is online and try again.\n")
        if not me and tries >= 5:
            sys.exit("Stopping here. Paste the install command again to retry, or send me the message above.")
    print(f"  Token works: your bot is @{me['username']}.")
    config.set_value("telegram_token", s.telegram_token)
    if not s.telegram_chat_id:
        print(f"\nNow open your bot in Telegram: https://t.me/{me['username']} and press Start (or send 'hi').")
        print("Waiting for your message", end="", flush=True)
        for _ in range(100):  # ~5 minutes
            try:
                updates = notify._call(s, "getUpdates").get("result", [])
            except Exception:
                updates = []
            chats = [u["message"]["chat"]["id"] for u in updates if "message" in u]
            if chats:
                s.telegram_chat_id = str(chats[-1])
                break
            print(".", end="", flush=True)
            time.sleep(3)
        print()
        if not s.telegram_chat_id:
            sys.exit("Didn't see a message. Send your bot 'hi', then paste the install command again.")
        config.set_value("telegram_chat_id", s.telegram_chat_id)
    print("Telegram is connected. You'll only hear from it when Claude confirms a real good deal.\n")

    print("== Claude: checks photos and real prices of the good finds ==")
    if shutil.which(s.claude_bin):
        print("Claude Code is installed. If you've never logged in, type  claude  once, log in, then /exit.")
        print("Then  flipperbot claude-test  checks the bot can use it.")
    else:
        print("Claude Code isn't installed (optional). To add it, paste this, then type  claude  and log in:")
        print("  curl -fsSL https://claude.ai/install.sh | bash")
    print()
    if sys.platform == "darwin":
        answer = input("Start flipperbot now, in the background, and every time you log in? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes", "d", "da"):
            import subprocess
            import time

            try:
                web._url_file().unlink()  # the bot writes the address it really gets
            except OSError:
                pass
            autostart.enable()
            for _ in range(30):  # wait for the background bot's dashboard to come up
                if web.is_flipperbot(web.url(s)):
                    break
                time.sleep(1)
            subprocess.run(["open", web.url(s)], capture_output=True)
            print(f"\nYour dashboard: {web.url(s)}  (it just opened in your browser)")
            try:
                from . import macapp

                app = macapp.make()
                print(f"One-click app: {app}. Click Flipperbot (in Applications, Launchpad or Spotlight) to open the")
                print("dashboard, starting the bot first if it isn't running. Drag it to the Dock to keep it there.")
            except Exception as e:
                print(f"(Couldn't make the Flipperbot app: {e}. `flipperbot make-app` tries again.)")
            return
    print("All set. Start the bot with:  flipperbot run")


def _rescore(db: DB, s: config.Settings) -> None:
    before: dict[str, int] = {}
    for r in db.all():
        l = bot.row_to_listing(r)
        if bot.is_relevant(l):
            bot.evaluate(db, l, s, ebay_cached_only=True)
        else:
            db.conn.execute("UPDATE listings SET tier='bad', reason=? WHERE key=?", (f"not a {niches.get(l.niche).noun}", l.key))
    db.conn.commit()
    for r in db.conn.execute("SELECT tier, COUNT(*) n FROM listings GROUP BY tier"):
        before[r["tier"]] = r["n"]
    print("tiers now:", dict(sorted(before.items(), key=lambda kv: -TIER_RANK.get(kv[0] or "bad", 0))))


if __name__ == "__main__":
    main()
