# Plan

## What we agreed

- Watches first, budget under 5000 lei, start with cheap ones, broken ones that are worth fixing, lots.
- All of Romania (OLX delivery). Polling every 5–10 minutes. Telegram alerts.
- Runs on Arnold's Mac for now. OLX refuses cloud servers (403 from the dev container).
- Tiers: bad (skip), mid (second look: daily summary + re-judged on price drops),
  good and real good (alert + Claude check). Cheap luxury = suspect (likely fake).
- AI = Claude Code headless (`claude -p`) on the Mac, on the $20 subscription, so capped
  (15 checks a day by default). It reads the photos and web-searches prices: that's the
  "just google it" and "reverse image search" step, for free.
- No messages to sellers.

## Prices: there is no free watch-price API

Chrono24 has no public API and blocks bots; WatchCharts has one but it's paid; eBay's free API
only shows asking prices. So:

1. **Our own price book** (done): every listing the bot sees is stored; a model's market price
   is the median asking price of its working, single listings. `backfill` seeds it.
2. **Claude's web search** (done) for good / real good listings.
3. Later: a second source for mids (Chrono24 or eBay asking prices, fetched rarely).

## The repos you linked

| repo | what it is | verdict |
|---|---|---|
| kjanus03/olx-scrapper | Real, but for **olx.pl**; parses page HTML. | Borrowed ideas: accessory filter, outlier filter, price-drop tracking. |
| mirelconstantin/olx-scraper | olx.ro **rentals**; relies on generated CSS class names (`css-qfzx1y`) that change on every OLX redeploy. | Not useful. |
| data-scrape/facebook-marketplace-scraper | **Fake**: `scrape()` fetches example.com and keeps the page `<title>`. README advertises a paid scraping service. | Don't use. |
| josh-56/facebook-marketplace-scraper | **Fake**: invented class names, and the files start with a stray `thon` so they can't even run. | Don't use. |
| danyk20/facebook-marketplace-scraper | **The real one.** Headless Chromium (Playwright), stays logged in through a saved browser profile, reads Facebook's own JSON while scrolling, well tested, maintained. On PyPI. | Use it for Facebook. |

Instead of parsing OLX's HTML, flipperbot reads `https://www.olx.ro/api/v1/offers/`, the JSON
API the OLX site itself uses: exact price and currency, "price dropped from", all photos, seller,
delivery. No markup to break.

## Done (phase 1, not yet run against live OLX)

- `sources/olx.py`: OLX API search + parsing.
- `identify.py`, `watchdb.py`: brand (~100 brands in 6 segments), reference numbers, model families,
  flags (broken, battery, lot + count, replica, "cumpar", repair-shop ads, parts, solid gold, box & papers).
- `tiers.py`: the tiers above.
- `db.py`: SQLite, price history, price book.
- `notify.py`: Telegram. `ai.py`: Claude check. `bot.py`, `cli.py`: polling loop and commands.
- Tests on Romanian-style titles and hand-written OLX responses (46 passing).

## Next

1. **Run on the Mac** (`poll`, then `backfill`): check the real API matches the parser. Save a real
   response into `samples/` (see samples/README.md) so the tests use it. Tune brand list, keywords,
   thresholds from what real listings look like.
2. **Facebook Marketplace** with danyk20's scraper, on a **second** Facebook account, every 30–60 min.
   Needs: a Romania entry in its `COUNTRY_ANCHORS` (it ships Switzerland only), and its browser is
   hard-coded to `de-CH`, so login button texts need Romanian/English.
3. Okazii.ro (auctions ending cheap), Publi24, Lajumate, Vinted.
4. Mids: second price source; listings that sit unsold for weeks (negotiation targets).
5. Learn from outcomes: mark what you bought and what it sold for, and tune the tiers from that.
