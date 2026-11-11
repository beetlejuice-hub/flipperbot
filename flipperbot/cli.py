"""flipperbot <command>

  run              poll forever (every 5-10 min), alert, AI-check, daily summary at 20:00
  poll             one poll, then exit
  backfill         read many pages for every search term once, to build the price book (no alerts)
  rescore          judge every stored listing again (after backfill or after changing settings)
  show             list stored listings by tier
  digest           send the daily summary now
  ai <url|key>     run the Claude check on one stored listing now
  telegram-setup   find your Telegram chat id after you've messaged your bot
  stats            what's in the database
"""

from __future__ import annotations

import argparse
import json
import sys

from . import ai, bot, config, notify
from .db import DB, TIER_RANK
from .sources import olx


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="flipperbot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
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
    args = p.parse_args(argv)

    s = config.load()
    db = DB(s.db_path)

    if args.cmd == "run":
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
