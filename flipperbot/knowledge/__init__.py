"""Category knowledge: what moves prices, sleeper brands, fakes, reselling tips. Markdown files the
AI checks read: the whole file for the full check (as its system prompt, which Claude caches), the
"Cheat sheet" section for the cheap quick read."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).parent


@lru_cache(maxsize=None)
def full(niche: str) -> str:
    path = HERE / f"{niche}.md"
    text = path.read_text() if path.exists() else ""
    return re.sub(r"\n## Sources.*", "", text, flags=re.S).strip()


@lru_cache(maxsize=None)
def cheat_sheet(niche: str) -> str:
    m = re.search(r"## Cheat sheet[^\n]*\n(.*?)(?=\n## )", full(niche), re.S)
    return m.group(1).strip() if m else ""
