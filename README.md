# flipperbot

Watches OLX.ro for underpriced watches (single ones, lots, broken ones),
sorts every listing into **bad / suspect / mid / good / real good**, and shows them
on a dashboard. Claude (on your Claude subscription) reads the real good ones'
descriptions and photos and checks what the model really sells for; only the deals
it confirms are sent to your phone on Telegram.

Runs on your Mac, in the background.

## Install (once, ~5 minutes)

1. Open **Terminal**: press ⌘ + Space, type `Terminal`, press Enter.
2. Paste this and press Enter:

   ```bash
   curl -LsSf https://raw.githubusercontent.com/beetlejuice-hub/flipperbot/claude/practical-cannon-luzypm/install.sh | sh
   ```

3. It walks you through Telegram: open **@BotFather** in Telegram, send `/newbot`, pick a name,
   paste the token it gives you, then press **Start** in your new bot. It finds the rest by itself.
4. Answer **Enter** to "Start flipperbot now…". Done: it runs in the background, starts again
   whenever you log in, and opens your dashboard (usually http://localhost:8789). Telegram stays quiet
   until Claude confirms a real good deal.

It ships with a starter price book, so it knows market prices from its first check.

**Optional, Claude checks** of the good finds (photos, fakes, real resale prices), on your Claude plan:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Then type `claude`, log in, type `/exit`. The bot uses it by itself from then on (max 15 a day).

## Using it

**One click: the Flipperbot app** (in Applications, Launchpad or Spotlight; drag it to the Dock to keep
it there). Clicking it starts the bot if it isn't running and opens the dashboard. The bot also starts
by itself whenever you log in, so mostly you only click it to look at deals. (No app yet? `flipperbot make-app`.)

**Dashboard: http://localhost:8789** on the Mac (bookmark it; if another app already uses that port, it takes the next free one; `flipperbot open` always finds it). Every deal with its photo, price,
why the bot rated it, and Claude's verdict. Tabs for Deals, Maybe, Likely fake, Starred, Claude
checked; buttons to star, hide, or *Ask Claude* about any listing. It's served by the bot itself,
so it's there whenever the bot runs. `flipperbot open` opens it.

**Telegram stays quiet except for confirmed deals.** A real good deal is sent only after Claude has
read its description and photos and says: not fake, buy or negotiate, and at least 50% sure
(`alert_min_confidence`). One message: the deal and Claude's notes (how sure, real or fake, condition,
resale, what to offer). Everything else, including real good deals Claude didn't confirm, is on the
dashboard with Claude's notes. A real good deal waiting for Claude (daily limit used up) is checked at
the next chance. Claude also checks good ones on the dashboard with what's left of the day's budget. (To open the dashboard on your phone too, on the same Wi-Fi, set
`dashboard_lan = true` in the settings file; then it's at `http://<your-mac-name>.local:8789`.
Anyone on that Wi-Fi could see it, so only at home.)

From Terminal:

| command | what it does |
|---|---|
| `flipperbot open` | open the dashboard (same as clicking the app, without starting the bot) |
| `flipperbot show` | the best listings found, with why |
| `flipperbot show --tier mid -n 100` | one tier |
| `flipperbot ai <olx link>` | Claude-check one listing now |
| `flipperbot log` | what the bot is doing right now (Ctrl + C to leave) |
| `flipperbot stop` / `flipperbot start` | turn the background bot off / on |
| `flipperbot stats` | what's in the database |
| `flipperbot rescore` | re-judge everything (after changing thresholds) |

Settings live in `~/.flipperbot/config.toml`; the database, photos and log in `~/.flipperbot/`.
The Mac has to be awake for it to work: it keeps itself from idle sleep, but closing the lid pauses it.

To update to the newest version, paste the install command again.

## Is it safe to run?

- **No extra packages.** The bot only uses Python's own standard library: nothing third-party
  gets installed. uv and Claude Code come from their makers' official installers. `install.sh`
  is 20 lines: read it before running if you like.
- **It only talks to**: OLX (listings and photos), Telegram (your alerts), and Claude Code on
  your Mac. The dashboard is only reachable from the Mac itself (unless you turn on `dashboard_lan`),
  and other websites can't use it.
- **It never logs in anywhere**, never contacts sellers, never buys anything.
- **Claude is locked down.** Listing text is written by strangers, so a listing could try to
  give Claude instructions. Claude is told the text is just data, and it's started with only two
  tools: reading the photos and web search. No shell, no file edits, no opening web pages, so it
  can't act on a malicious listing or send anything anywhere (see `CLAUDE_ARGS` in `flipperbot/ai.py`).
- **OLX's rules**: like most marketplaces, OLX's terms most likely forbid automated collection.
  The bot reads public listings through the same data feed the OLX website uses, a few requests every
  5–10 minutes. The realistic worst case is OLX blocking your home IP for a while.

**Lots** (several watches sold together, often old and unnamed) are where good watches hide, so Claude
goes through every one: photos at full size, each cut into four zoomed quarters, watch by watch (dial
text, logos, movements), naming and valuing each and checking with web search. If its total makes the
lot a real good deal and it's confident, you get it on Telegram with the watches that make it worth it.

**Fakes.** Most cheap luxury watches online in Romania are replicas, so the bot is suspicious first:
- replica words and factory names (AAA, 1:1, clone, noob, VSF, clean factory...) → skipped;
- a Japanese/Chinese movement in a Swiss/luxury watch, or replica-shop talk on a luxury brand ("many
  models", "gift box", "last pieces") → *likely fake*;
- one seller with a row of cheap modern luxury/Swiss watches → *likely fake* (vintage shops excepted);
- every real good deal is Claude-checked with a brand-by-brand checklist, the seller's other listings,
  and a stricter bar for luxury/Swiss (60% sure). Its Telegram message says what to ask the seller.

**Old watches and people who don't know what they sell.** Most searches go to lots, old, inherited and
broken watches ("ceasul bunicului", "mostenire", "din pod", "vechituri", pocket watches...). Old watches
where the model isn't clear, and sellers who write "nu stiu ce marca", "de la bunicul", "nu ma pricep", go
to Claude (after lots), which identifies them from dial, case and movement and values them.

## How it decides

See `flipperbot/tiers.py`. In short: once 4+ listings of the same model are in the
database, their median asking price is "market". Resale = market × 0.85 (things sell under
asking), minus repair (a battery ~40 lei, a broken Seiko ~250, a broken Swiss ~600).

| tier | rule (default) | what happens |
|---|---|---|
| real good | ≥50% under market and ≥300 lei profit | Claude checks it; Telegram only if Claude confirms (≥50% sure) |
| good | ≥30% under and ≥150 lei profit; or broken/lot luxury | dashboard; Claude checks with leftover budget |
| mid | ≥15% under; or interesting but no price history; every lot | dashboard ("Maybe"), re-judged if the price drops |
| suspect | luxury brand far too cheap, or a seller with a row of them | dashboard ("Likely fake") |
| bad | fashion brands, replicas, "cumpar" ads, parts, over budget, not cheap | ignored |

Tune all of it in `~/.flipperbot/config.toml`, then `flipperbot rescore`.

## Development

```bash
git clone https://github.com/beetlejuice-hub/flipperbot && cd flipperbot
uv run flipperbot poll          # one check, prints what it finds
uv run flipperbot backfill      # rebuild the price book (~30 min)
uv run flipperbot export-seed   # ship it as the starter price book
```

## Tests

```bash
uv run --with pytest pytest
```
