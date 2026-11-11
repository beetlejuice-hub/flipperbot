"""flipperbot <command>

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
  start / stop     (Mac) run in the background from login on / stop that
  log              (Mac) follow what the background bot is doing
"""

from __future__ import annotations

import argparse
import json
import sys

from . import ai, autostart, bot, config, notify, seed
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
        rows = bot.poll(db, s)
        bot.run_ai(db, rows, s)

    elif args.cmd == "backfill":
        for i, term in enumerate(s.search_pool):
            print(f"[{i + 1}/{len(s.search_pool)}] {term}")
            try:
                listings = bot.fetch_all([(term, None)], s, pages=args.pages)
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
        res = ai.check(db, row, s)
        print(json.dumps(res, indent=2, ensure_ascii=False))
        if res:
            notify.send(s, notify.ai_text(db.get(row["key"]), res))

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
    if not s.telegram_token:
        print("1. In Telegram, search for @BotFather and open it.")
        print("2. Send it:  /newbot")
        print("3. It asks for a name, then a username ending in 'bot' (e.g. arnold_flipper_bot).")
        print("4. It answers with a token: a long code like 123456789:AAH...\n")
        s.telegram_token = input("Paste the token here and press Enter: ").strip()
    try:
        me = notify._call(s, "getMe")["result"]
    except Exception:
        sys.exit("That token didn't work. Copy it again from @BotFather and rerun: flipperbot setup")
    config.set_value("telegram_token", s.telegram_token)
    if not s.telegram_chat_id:
        print(f"\nNow open your bot in Telegram: https://t.me/{me['username']} and press Start (or send 'hi').")
        print("Waiting for your message", end="", flush=True)
        for _ in range(100):  # ~5 minutes
            updates = notify._call(s, "getUpdates").get("result", [])
            chats = [u["message"]["chat"]["id"] for u in updates if "message" in u]
            if chats:
                s.telegram_chat_id = str(chats[-1])
                break
            print(".", end="", flush=True)
            time.sleep(3)
        print()
        if not s.telegram_chat_id:
            sys.exit("Didn't see a message. Send your bot 'hi' and run: flipperbot setup")
        config.set_value("telegram_chat_id", s.telegram_chat_id)
    notify.send(s, "✅ flipperbot is connected. Deals will show up here.")
    print("Telegram works: check your phone.\n")

    print("== Claude: checks photos and real prices of the good finds ==")
    if shutil.which(s.claude_bin):
        print("Claude Code is installed. If you've never logged in, type  claude  once, log in, then /exit.")
    else:
        print("Claude Code isn't installed (optional). To add it, paste this, then type  claude  and log in:")
        print("  curl -fsSL https://claude.ai/install.sh | bash")
    print()
    if sys.platform == "darwin":
        answer = input("Start flipperbot now, in the background, and every time you log in? [Y/n] ").strip().lower()
        if answer in ("", "y", "yes", "d", "da"):
            autostart.enable()
            notify.send(s, "🚀 flipperbot started. Checking OLX every 5-10 minutes.")
            return
    print("All set. Start the bot with:  flipperbot run")


def _rescore(db: DB, s: config.Settings) -> None:
    before: dict[str, int] = {}
    cats = bot.watch_categories(db)
    for r in db.all():
        l = bot.row_to_listing(r)
        if bot.is_watch(l, cats):
            bot.evaluate(db, l, s)
        else:
            db.conn.execute("UPDATE listings SET tier='bad', reason='not a watch' WHERE key=?", (l.key,))
    db.conn.commit()
    for r in db.conn.execute("SELECT tier, COUNT(*) n FROM listings GROUP BY tier"):
        before[r["tier"]] = r["n"]
    print("tiers now:", dict(sorted(before.items(), key=lambda kv: -TIER_RANK.get(kv[0] or "bad", 0))))


if __name__ == "__main__":
    main()
