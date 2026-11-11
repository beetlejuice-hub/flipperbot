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
