# flipperbot

Watches OLX.ro for underpriced watches (single ones, lots, broken ones),
sorts every listing into **bad / suspect / mid / good / real good**, and sends
the good ones to your phone on Telegram. Claude then looks at the photos of
those and searches the web for what that model really sells for, using your
Claude subscription.

Runs on your Mac. OLX blocks cloud servers, so it has to run from home.

## Setup on the Mac (once)

1. Install uv (it runs Python projects, no other installs needed):

   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. Get the code:

   ```bash
   git clone https://github.com/beetlejuice-hub/flipperbot && cd flipperbot
   ```

3. Check that OLX answers and the bot understands it. This does one poll and prints what it found:

   ```bash
   uv run flipperbot poll
   ```

4. Build the price book: reads ~5 pages for every search term once, no alerts. Takes ~25 minutes.

   ```bash
   uv run flipperbot backfill
   ```

5. Telegram alerts: on Telegram, message **@BotFather**, send `/newbot`, pick a name, copy the token.

   ```bash
   mkdir -p ~/.flipperbot && cp config.example.toml ~/.flipperbot/config.toml && open -e ~/.flipperbot/config.toml
   ```

   Paste the token as `telegram_token`, save. Send your new bot any message on Telegram, then:

   ```bash
   uv run flipperbot telegram-setup
   ```

   Put the chat id it prints into the config as `telegram_chat_id`.

6. Claude checks: Claude Code must be installed and logged in on the Mac (`claude` in a terminal
   should open it). The bot runs it headless for good and real-good listings, max 15 a day
   (`ai_daily_limit`), on your subscription.

## Running it

```bash
caffeinate -i uv run flipperbot run
```

`caffeinate -i` keeps the Mac from sleeping while it runs. It polls every 5–10 minutes,
alerts on good and real good, has Claude check one listing per poll, and sends the
daily second-look summary (mids, suspects) at 20:00.

Other commands:

| command | what it does |
|---|---|
| `uv run flipperbot show` | the best listings found, with why |
| `uv run flipperbot show --tier mid -n 100` | one tier |
| `uv run flipperbot ai <olx url>` | Claude-check one listing now |
| `uv run flipperbot rescore` | re-judge everything (after changing thresholds) |
| `uv run flipperbot stats` | what's in the database |
| `uv run flipperbot digest` | send the summary now |

Data lives in `~/.flipperbot/` (database, downloaded photos, config).

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
