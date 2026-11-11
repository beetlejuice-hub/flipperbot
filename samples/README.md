# Real OLX responses

Saved responses from OLX, used by the tests (`tests/test_olx_and_bot.py`) when present.
They hold sellers' names, so they stay out of git (`.gitignore`). Save one with:

```bash
uv run python -c "import json; from flipperbot.sources import olx; json.dump(olx._post(olx.search_params('ceas')), open('samples/olx-ceas.json', 'w'), ensure_ascii=False)"
```
