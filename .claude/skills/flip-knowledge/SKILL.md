---
name: flip-knowledge
description: Category knowledge for flipping second-hand watches (incl. smartwatches) and cameras/lenses bought in Romania - what moves prices, sleeper brands and references worth money, fake and franken tells, condition checks, reselling costs and where to sell. Use when judging a listing, tuning flipperbot's rules (watchdb.py, camdb.py, identify.py, tiers.py, scoring.py), or writing its AI prompts.
---

# Flip knowledge

The knowledge lives in `flipperbot/knowledge/` so the bot's own AI checks use the same text:

- `flipperbot/knowledge/watches.md`: the detailed one (value drivers, sleepers, Seiko/Omega/Soviet/pocket/
  smartwatch specifics, fakes by brand, reselling tips).
- `flipperbot/knowledge/cameras.md`: cameras and lenses.

Each file has a "Cheat sheet" section (the cheap quick AI read gets only that) and the full text (Claude's
full listing check gets it as its system prompt). Read the relevant file before judging a listing or changing
the rules. When you learn something new (a new fake pattern, a sleeper reference, a price driver), add it to the
file, and if it can be a free rule, also to `watchdb.py` / `camdb.py` / `identify.py` with a test.
