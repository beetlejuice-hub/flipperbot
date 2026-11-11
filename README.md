# flipperbot

Watches OLX.ro for underpriced watches (single ones, lots, broken ones),
sorts every listing into **bad / suspect / mid / good / real good**, and sends
the good ones to your phone on Telegram. Claude then looks at the photos of
those and searches the web for what that model really sells for, using your
Claude subscription.

Runs on your Mac, in a Terminal window you leave open.

## Setup, step by step (once, ~20 minutes)

**Open Terminal**: press ⌘ + Space, type `Terminal`, press Enter. You paste each command
below into it and press Enter. Wait for one to finish before the next.

**1. Get the code onto your Mac.** The repo is private, so the easiest way is GitHub Desktop:
download it from desktop.github.com, sign in, then *File → Clone Repository → flipperbot → Clone*.
It lands in `Documents/GitHub/flipperbot`. Then in Terminal:

```bash
cd ~/Documents/GitHub/flipperbot
```

**2. Install uv**, the tool that runs the bot (it fetches the right Python by itself; no admin password needed):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close Terminal and open it again (so it finds uv), and `cd ~/Documents/GitHub/flipperbot` again.

**3. Try it.** One search round; it prints what it finds:

```bash
uv run flipperbot poll
```

**4. Teach it prices.** Reads ~5 pages for each of ~50 searches, slowly. ~25 minutes, no alerts:

```bash
uv run flipperbot backfill
```

**5. Telegram, so alerts reach your phone.**
- In Telegram, search **@BotFather**, send `/newbot`, give it any name. It replies with a *token* (a long code).
- Make the settings file and open it:

  ```bash
  mkdir -p ~/.flipperbot && cp flipperbot/config.example.toml ~/.flipperbot/config.toml && open -e ~/.flipperbot/config.toml
  ```

- Paste the token between the quotes after `telegram_token =`, save (⌘S), close.
- In Telegram, open your new bot and send it "hi". Then:

  ```bash
  uv run flipperbot telegram-setup
  ```

- It prints a chat id. Put it after `telegram_chat_id =` in the same file, save.

**6. Claude checks (optional, uses your Claude plan).** Install Claude Code and log in once:

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

Then type `claude`, log in with your Claude account, and quit it (`/exit`). The bot uses it by itself
from then on, up to 15 checks a day.

## Running it

```bash
caffeinate -i uv run flipperbot run
```

Leave that Terminal window open. `caffeinate -i` stops the Mac sleeping while it runs. Every 5–10
minutes it checks OLX, alerts you on good and real good finds, has Claude check one of them, and at
20:00 sends a summary of the "maybe" ones. Stop it with Ctrl + C.

Other commands:

| command | what it does |
|---|---|
| `uv run flipperbot show` | the best listings found, with why |
| `uv run flipperbot show --tier mid -n 100` | one tier |
| `uv run flipperbot ai <olx link>` | Claude-check one listing now |
| `uv run flipperbot rescore` | re-judge everything (after changing thresholds) |
| `uv run flipperbot stats` | what's in the database |
| `uv run flipperbot digest` | send the summary now |

Data lives in `~/.flipperbot/` (database, downloaded photos, config).

## Is it safe to run?

- **No extra packages.** The bot only uses Python's own standard library: nothing third-party
  gets installed. uv and Claude Code come from their makers' official installers.
- **It only talks to**: OLX (listings and photos), Telegram (your alerts), and Claude Code on
  your Mac.
- **It never logs in anywhere**, never contacts sellers, never buys anything.
- **Claude is locked down.** Listing text is written by strangers, so a listing could try to
  give Claude instructions. Claude is told the text is just data, and it's started with only two
  tools: reading the photos and web search. No shell, no file edits, no opening web pages, so it
  can't act on a malicious listing or send anything anywhere (see `CLAUDE_ARGS` in `flipperbot/ai.py`).
- **OLX's rules**: like most marketplaces, OLX's terms most likely forbid automated collection.
  The bot reads public listings through the same data feed the OLX website uses, a few requests every
  5–10 minutes. The realistic worst case is OLX blocking your home IP for a while.

## How it decides

See `flipperbot/tiers.py`. In short: once 4+ listings of the same model are in the
database, their median asking price is "market". Resale = market × 0.85 (things sell under
asking), minus repair (a battery ~40 lei, a broken Seiko ~250, a broken Swiss ~600).

| tier | rule (default) | what happens |
|---|---|---|
| real good | ≥50% under market and ≥300 lei profit | Telegram now, then Claude |
| good | ≥30% under and ≥150 lei profit; or broken/lot luxury | Telegram now, then Claude |
| mid | ≥15% under; or interesting but no price history | daily summary, re-judged if the price drops |
| suspect | luxury brand far too cheap | daily summary, flagged as likely fake |
| bad | fashion brands, replicas, "cumpar" ads, parts, over budget, not cheap | ignored |

Tune all of it in `~/.flipperbot/config.toml`, then `flipperbot rescore`.

## Tests

```bash
uv run --with pytest pytest
```
