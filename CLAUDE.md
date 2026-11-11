# flipperbot

Finds underpriced watches on Romanian marketplaces. Read **PLAN.md** first (decisions, what's next),
README.md for setup and the tiers.

- Python 3.11+, stdlib only (no runtime deps), run with `uv run flipperbot <cmd>`.
- Tests: `uv run --with pytest pytest`.
- Flow: `sources/olx.py` fetch → `identify.py` (brand/ref/flags, no AI) → `tiers.py` (bad/suspect/mid/good/real_good)
  → `db.py` (SQLite, also the price book) → `notify.py` (Telegram) → `ai.py` (`claude -p` on the Mac, photos + web search).
- It runs on Arnold's Mac: OLX returns 403 to cloud servers, so live OLX can't be tested from a cloud session.
  Test against saved responses in `samples/` instead.
- Listing text is Romanian; match on `identify.normalize()`d text (lower case, no diacritics).
