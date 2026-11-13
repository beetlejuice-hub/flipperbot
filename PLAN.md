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

More repos found (November 2026):

| repo | what it is | verdict |
|---|---|---|
| zandaulion/olx-deal-finder | Real, active OLX.ro deal finder (phones). Reads `/api/v1/offers/` and gets past OLX's 403 by imitating Chrome's network fingerprint (curl_cffi). | Its scoring idea (under Q1, ≥20% under median, a price floor) matches ours. We don't imitate a browser: see below. |
| FlorinPopaCodes/aeron-miller-index | Daily OLX.ro price tracker, runs on GitHub's servers through OLX's GraphQL gateway with a plain client. | **Adopted the gateway.** |
| Westeru/Romania-OLX-scraper | HTML + Gemini, Windows scripts. | Nothing new. |
| Giglium/vinted_scraper | Maintained Vinted package. | For Vinted, later. |
| passivebot/facebook-marketplace-scraper | Popular (400★) but last updated 2024. | danyk20 is better. |
| Chrono24 scrapers | All 2022–24, Chrono24 is behind Cloudflare now. | Not useful. |

**How flipperbot reads OLX:** `https://www.olx.ro/apigateway/graphql`, the GraphQL gateway the OLX
website itself uses, with a plain request. It returns the same fields as the REST API: exact price
(already in lei), "price dropped from", all photos, seller, delivery, OLX's own brand field. Checked
live: it answers normally even from a cloud server, while `/api/v1/offers/` answers 403.
Watch categories: 1677 = men's, 1676 = women's; each poll reads the newest of both plus a few
random searches.

## Done (phase 1, tested against live OLX on 2026-11-11)

- `sources/olx.py`: OLX API search + parsing.
- `identify.py`, `watchdb.py`: brand (~100 brands in 6 segments), reference numbers, model families,
  flags (broken, battery, lot + count, replica, "cumpar", repair-shop ads, parts, solid gold, box & papers).
- `tiers.py`: the tiers above.
- `db.py`: SQLite, price history, price book.
- `notify.py`: Telegram. `ai.py`: Claude check. `bot.py`, `cli.py`: polling loop and commands.
- Tests on Romanian titles and OLX-shaped responses (55 passing).
- Live sample (~650 real listings) checked by hand; fixed what it showed: dashboard and wall clocks,
  "AP x Swatch", "superclone", parts sold alone, swap-brand lists in titles ("sch. Seiko citizen…"),
  brand-only prices (now never above mid), cheap vintage/pocket luxury (now a Claude check, not "fake").
- Known rough edge: model families are broad (Seamaster = 90s quartz Polaris and modern 300M alike),
  so a family price can be far off. Claude's check catches it; references fix it as data grows.

- Install: `install.sh` (one pasted command) → `flipperbot setup` (guided Telegram) → background
  launchd agent (`flipperbot start/stop/log`). Ships a starter price book (`flipperbot/seed/`), built
  here from a full backfill, without descriptions or seller data.

## Next

1. **Arnold runs the installer on the Mac**; tune from a week of real alerts. Refresh the starter
   price book now and then (`backfill` + `export-seed`).
2. **Facebook Marketplace** with danyk20's scraper, on a **second** Facebook account, every 30–60 min.
   Needs: a Romania entry in its `COUNTRY_ANCHORS` (it ships Switzerland only), and its browser is
   hard-coded to `de-CH`, so login button texts need Romanian/English.
3. Other marketplaces: Publi24 and Lajumate are read (plain requests). Okazii (403), Vinted (its search API 403s
   without a browser session) and eMAG (511) refuse plain requests: not read, by the no-browser-imitation rule.
   Vinted would need an official route (an API key/partner program) or the person's own browser.
4. Mids: second price source; listings that sit unsold for weeks (negotiation targets).
5. Learn from outcomes: mark what you bought and what it sold for, and tune the tiers from that.
6. **More categories, picked with the dashboard's category boxes**: consoles and PC parts (now only on the
   trend radar's watchlist), LEGO, then sneakers/clothes. Sneakers sell on Vinted (vinted.ro) and OLX:
   Fuyucch1/Vinted-Notifications shows how Vinted's catalog search is read; check it answers plain
   requests before relying on it, as with OLX (no browser imitation).
7. **Seller reputation** (idea from BoPeng/ai-marketplace-monitor): OLX account age, number of listings,
   business flag into the score and the Claude check: new accounts and dealers posing as private sellers.
8. **Price history per model**: a weekly median snapshot per model, so the radar's "rising" uses a real
   series instead of first-seen dates, and the dashboard can draw a small line per model.
9. Google Trends interest over time per watchlist item (flack0x/trendspyg does it; ours reads only the
   daily "trending now" RSS today). eBay Marketplace Insights (sold prices) needs eBay's approval: apply.
