# flipperbot

Finds underpriced watches on Romanian marketplaces. Read **PLAN.md** first (decisions, what's next),
README.md for setup and the tiers.

- Python 3.11+, stdlib only (no runtime deps), run with `uv run flipperbot <cmd>`.
- Tests: `uv run --with pytest pytest`.
- Flow: `sources/olx.py` fetch → `identify.py` (brand/ref/flags, no AI) → `tiers.py` (bad/suspect/mid/good/real_good)
  → `db.py` (SQLite, also the price book) → `notify.py` (Telegram) → `ai.py` (`claude -p` on the Mac, photos + web search).
- OLX is read through its GraphQL gateway (`sources/olx.py`), which answers plain requests, also from
  cloud sessions. Its REST API (`/api/v1/offers/`) answers 403. Don't imitate a browser to get around that.
- `ai.py` runs Claude with only Read + WebSearch: listing text is untrusted. Keep it that way.
- Listing text is Romanian; match on `identify.normalize()`d text (lower case, no diacritics).
- Category knowledge (value drivers, sleeper brands, fakes, reselling): `flipperbot/knowledge/*.md`, also the
  `flip-knowledge` skill. The AI checks read it; keep rules (`watchdb.py`, `camdb.py`, `techdb.py`) in step with it.
- Categories (`niches.py`): watches, bikes, electronics, phones, tools, lego, sneakers, clothing, cool (cameras still known,
  off by default; `niche_budgets` can cap a category's price); each poll covers a few
  in turn (`niches_per_poll`; `every_poll`: watches, clothing and cool always). Catalog categories (`techdb.py`, `phonedb.py`, `tooldb.py`, `legodb.py`,
  `sneakerdb.py`, via `identify._identify_catalog`) price by exact model and variant, used private listings only.
- Smartwatches and bands: `smartdb.py` names the exact model (huawei|band 10, apple|watch series 9...). New prices in
  shops (`retail.py`, from Claude's checks and a daily web-search batch) cap every estimate; brand-only listings get
  no price at all.
- Men's clothing (`clothdb.py`, `knowledge/clothing.md`): brand tier (grail/luxury/premium/basic/fast), kind of item and
  the line that sets the price (moncler|maya, arc'teryx|beta lt, stone island|hoodie). Replicas: seller slang, a
  disguised brand name ("mo n cler"), shop-like listings, price floors; often-faked brands get the careful photo check and
  the clothing fake hunt (`ai.FAKE_HUNT_CLOTHES`).
- Sources: OLX (also tells which listings are gone: `bot.check_sold`), Publi24, Lajumate (`sources/`), Facebook.
  Okazii, Vinted and eMAG refuse plain requests: not read. Vinted answers its public page once, then shows Cloudflare's
  bot check; its API answers 403. Don't get around that (no browser imitation, no cookie tricks, no Vinted scraper
  libraries): Vinted items come in by hand (the dashboard's "Check a Vinted item"). OLX bumps and reposts are recognized (`db.upsert`).
- Claude use (`budget.py`): the bot's automatic calls come out of the person's plan. Mode Off / Economy (default: about a
  third of the config limits, fake check on Haiku, nothing 0:00-7:00) / Normal, switched on the dashboard (kv
  `claude_mode`); `budget.effective()` gives each round its settings. Today's calls and API-price cost from claude.log.
- The 0-10 score (`scoring.py`): 0 = removed, 1-7 free rules, quick AI (`quick.py`, haiku, text, batched),
  8+ full Claude check. Tests never call the real Claude (`tests/conftest.py`).
- Bicycles (`bikedb.py`, `knowledge/bikes.md`): brand + line (trek|marlin 7, rockrider|st 540), else brand + kind and
  wheel size; groupset and carbon read; the flip is buy tired, service, sell in spring (bike faults in `repairs.py`).
  Stolen-bike guards: "fara acte" on a good bike is suspect; half price for a premium one asks for invoice and serial.
- Cool finds (`cool.py`, niche "cool"): cheap, unusual things to keep, not flips, new or old (modern design by maker
  name in the title, art toys, gadgets, plants, vintage). A free score from style/material/oddness
  words and price (strong words count double), then a Haiku look at 2 photos scores how cool it is for the money. Own tab
  (✨), out of the flip lists, quick read and alerts.
- What sold (`market.py`): per model, the sold prices and range, days to sell, what the quick sales went for, how much
  sellers dropped (price history), the month's trend, a resale ask; brand-wide speed when the model has few sales. Shown
  on cards, in the Sold tab's "What sells", in Claude's prompt (`ai.sold_line`); offers follow the usual drop.
- Prices: sold listings are the hard evidence (3+ set the market, 1-2 count 3x an asking price); new (sealed, with
  tags) is compared with new ones or used ones + `bot.NEW_UPLIFT`. Faulty items: `repairs.py` reads the fault, the
  usual fix, its cost and odds, and prices it against working ones (`fixer` column, the 🔧 Fixer-uppers tab).
- Staying light: SQLite in WAL mode with indexes for the tabs (`db.INDEXES`), the schema checked once per process;
  `tidy.py` daily removes junk not seen for 2 weeks and anything not seen for 6 months (never starred, hidden, bought,
  Claude-checked or recently sold), old photos and big logs; the dashboard draws 40 cards at a time.
- Claude's check names the exact model from the photos; if it isn't the bot's, `bot.fix_model` re-keys the listing
  (`model_fix` column, kept on later polls) so its prices and the price book are for the right model.
