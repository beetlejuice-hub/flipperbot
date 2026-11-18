"""Listings you bring in by hand: a Vinted item (or any other) you found yourself.

Vinted doesn't let programs read it (its API answers 403 and its pages show Cloudflare's bot check), and the bot
doesn't get around that. So you look on Vinted as you always do, and when something looks good you paste it into
the dashboard: the link, title, price, description, and a few screenshots or saved photos. The bot then does what
it does with any listing: names the brand and line, prices it against similar ones, runs the fake rules, and (if
you ask) Claude checks the photos and labels on your Mac. Nothing is fetched from Vinted.
"""

from __future__ import annotations

import base64
import hashlib
import re
import shutil
from typing import Any
from urllib.parse import urlparse

from .config import Settings
from .db import DB, now
from .models import Listing

MAX_PHOTOS = 8
MAX_PHOTO_BYTES = 4_000_000
MAX_BODY_BYTES = 40_000_000  # 8 photos, base64
_VINTED_ITEM = re.compile(r"(?:^|\.)vinted\.[a-z.]+$")


class Invalid(ValueError):
    """What's wrong with what was pasted, in words for the person who pasted it."""


def source_and_id(url: str, title: str, price: int) -> tuple[str, str]:
    """vinted:<item id> for a Vinted item link, else manual:<a short hash of what was pasted>."""
    u = urlparse(url) if url else None
    if u and _VINTED_ITEM.search(u.hostname or ""):
        m = re.search(r"/items/(\d+)", u.path)
        if m:
            return "vinted", m.group(1)
    seed = url or f"{title}|{price}"
    return "manual", hashlib.sha1(seed.encode()).hexdigest()[:12]


def _photo(data_url: str) -> bytes:
    m = re.fullmatch(r"data:image/(?:jpeg|jpg);base64,([A-Za-z0-9+/=\s]+)", data_url or "")
    if not m:
        raise Invalid("photos must be JPEG images")
    raw = base64.b64decode(m.group(1), validate=False)
    if not raw.startswith(b"\xff\xd8") or len(raw) > MAX_PHOTO_BYTES:
        raise Invalid("a photo isn't a JPEG or is too big (4 MB at most)")
    return raw


def add(db: DB, s: Settings, data: dict[str, Any]) -> Any:
    """Store and judge a pasted listing. Returns its row. Raises Invalid with a reason."""
    from . import bot, niches

    title = re.sub(r"\s+", " ", str(data.get("title") or "")).strip()[:200]
    if len(title) < 3:
        raise Invalid("a title, please (as it is on Vinted)")
    try:
        price = int(round(float(str(data.get("price") or "").replace(",", "."))))
    except ValueError:
        raise Invalid("the price in lei, please") from None
    if price <= 0 or price > 1_000_000:
        raise Invalid("the price in lei, please")
    url = str(data.get("url") or "").strip()[:500]
    if url and urlparse(url).scheme not in ("http", "https"):
        raise Invalid("the link should start with https://")
    niche = str(data.get("niche") or "clothing")
    if niche not in niches.ALL or niche == "lots":
        raise Invalid("pick a category")
    photos = [_photo(p) for p in (data.get("photos") or [])[:MAX_PHOTOS]]
    description = str(data.get("description") or "")[:5000]
    size = str(data.get("size") or "").strip()[:20]
    if size and size.lower() not in description.lower():
        description = f"Marime: {size}\n{description}"

    source, source_id = source_and_id(url, title, price)
    key = f"{source}:{source_id}"
    folder = s.photos_dir / key.replace(":", "_")
    if photos:  # new photos replace the old ones (and Claude's zoomed quarters of them)
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True, exist_ok=True)
        for i, raw in enumerate(photos, 1):
            (folder / f"{i}.jpg").write_bytes(raw)
    count = len(photos) if photos else len(list(folder.glob("[0-9].jpg"))) if folder.exists() else 0
    l = Listing(source=source, source_id=source_id, url=url, title=title, description=description, price=price,
                price_ron=price, photos=[f"/api/photo/{key}/{i}" for i in range(1, count + 1)], created_at=now(),
                niche=niche, params={"added_by_hand": True})
    db.upsert(l)  # you chose it: no category filter
    return bot.evaluate(db, l, s, ebay_cached_only=True)


def photo_path(s: Settings, key: str, n: str) -> Any:
    """The file behind /api/photo/<key>/<n>, if it is one of a hand-added listing's photos."""
    if not re.fullmatch(r"(?:vinted|manual):[\w-]{1,40}", key) or not re.fullmatch(r"[1-9]", n):
        return None
    path = s.photos_dir / key.replace(":", "_") / f"{n}.jpg"
    return path if path.is_file() else None
