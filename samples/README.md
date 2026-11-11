# Real OLX responses

Saved responses from OLX's API, used by the tests (`tests/test_olx_and_bot.py`) when present.
They hold sellers' names, so they stay out of git (`.gitignore`). Capture one on the Mac:

```bash
curl -s "https://www.olx.ro/api/v1/offers/?offset=0&limit=40&query=ceas&sort_by=created_at:desc" -o samples/olx-ceas.json
```
