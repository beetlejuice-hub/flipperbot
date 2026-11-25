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
- Categories (`niches.py`): watches, bikes, electronics, phones, tools, lego, sneakers, clothing (cameras still known, off by
  default; `niche_budgets` caps a category's price, bikes 1,500 lei); each poll covers a few
  in turn (`niches_per_poll`; `every_poll`: watches and clothing always). Catalog categories (`techdb.py`, `phonedb.py`, `tooldb.py`, `legodb.py`,
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
- The 0-10 score (`scoring.py`): 0 = removed, 1-7 free rules, quick AI (`quick.py`, haiku, text, batched),
  8+ full Claude check. Tests never call the real Claude (`tests/conftest.py`).
- Bicycles (`bikedb.py`, `knowledge/bikes.md`): brand + line (trek|marlin 7, rockrider|st 540), else brand + kind and
  wheel size; groupset and carbon read; the flip is buy tired, service, sell in spring (bike faults in `repairs.py`).
  Stolen-bike guards: "fara acte" on a good bike is suspect; half price for a premium one asks for invoice and serial.
- Prices: sold listings are the hard evidence (3+ set the market, 1-2 count 3x an asking price); new (sealed, with
  tags) is compared with new ones or used ones + `bot.NEW_UPLIFT`. Faulty items: `repairs.py` reads the fault, the
  usual fix, its cost and odds, and prices it against working ones (`fixer` column, the 🔧 Fixer-uppers tab).
- Claude's check names the exact model from the photos; if it isn't the bot's, `bot.fix_model` re-keys the listing
  (`model_fix` column, kept on later polls) so its prices and the price book are for the right model.
