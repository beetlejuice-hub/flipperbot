"""Publi24.ro: Romania's second classifieds site. Its search page answers plain requests; each listing is an
`article-item` block with title, description start, location, date, price, link and first photo.

The page is read as text (no browser, no login). If Publi24 starts refusing plain requests, this source just
returns nothing: don't imitate a browser to get around that.
"""

from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from typing import Callable

from .. import net
from ..models import Listing

SEARCH = "https://www.publi24.ro/anunturi/?q={q}&pag={page}"
UA = "flipperbot/0.1 (personal price tracker)"

MONTHS = {"ian": 1, "feb": 2, "mar": 3, "apr": 4, "mai": 5, "iun": 6, "iul": 7, "aug": 8, "sep": 9, "oct": 10, "noi": 11,
          "nov": 11, "dec": 12}


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with net.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def _text(block: str, cls: str) -> str:
    """The text of the element with this class (up to the next article-* element)."""
    i = block.find(f'class="{cls}')
    if i < 0:
        return ""
    j = block.find('class="article-', i + len(cls) + 8)
    inner = block[i:j if j > 0 else i + 800].split(">", 1)[-1]
    inner = re.sub(r"<[^>]+>", " ", inner)
    inner = re.sub(r"<[a-z]+$", "", inner.strip())  # the next element's opening tag, cut in half
    return re.sub(r"\s+", " ", html.unescape(inner)).strip()


def parse_date(text: str, today: date | None = None) -> str:
    """'azi 10:38', 'ieri 12:22', '13 Septembrie', '13.09.2026' -> ISO date-time (Romania time, no zone)."""
    today = today or date.today()
    t = text.lower().strip()
    m = re.match(r"(azi|astazi|ieri)\s*(\d{1,2}):(\d{2})?", t)
    if m:
        d = today - timedelta(days=1 if m.group(1) == "ieri" else 0)
        return datetime(d.year, d.month, d.day, int(m.group(2)), int(m.group(3) or 0)).isoformat()
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    if m:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    m = re.match(r"(\d{1,2})\s+([a-z]{3})[a-z]*\.?(?:\s+(\d{4}))?", t)
    if m and m.group(2) in MONTHS:
        year = int(m.group(3)) if m.group(3) else today.year
        d = date(year, MONTHS[m.group(2)], int(m.group(1)))
        if d > today:  # "28 Decembrie" seen in January: last year
            d = date(year - 1, d.month, d.day)
        return datetime(d.year, d.month, d.day).isoformat()
    return ""


def _price(text: str, eur_to_ron: float) -> int | None:
    """'3 500 RON' -> 3500; a block with an old and a new price -> the last one; '1.200 EUR' -> lei."""
    found = re.findall(r"(\d[\d .]*)\s*(RON|LEI|EUR|€)", text, re.I)
    if not found:
        return None
    number, cur = found[-1]
    value = int(re.sub(r"[ .]", "", number))
    if value > 10_000_000:  # glued old + new prices, or a placeholder
        return None
    return round(value * eur_to_ron) if cur.upper() in ("EUR", "€") else value


def parse(page: str, eur_to_ron: float = 5.0, today: date | None = None) -> list[Listing]:
    out = []
    for block in page.split('class="article-item')[1:]:
        url = re.search(r'href="(https://www\.publi24\.ro/anunturi/[^"]+/anunt/[^"]+\.html)"', block)
        if not url:
            continue
        title = _text(block, "article-title")
        if not title:
            continue
        img = re.search(r'<img[^>]+src="(https://[^"]+)"', block)
        city = _text(block, "article-location")
        city = re.sub(r"^\d{1,2}\s+[A-Za-z]+,\s*", "", city)  # "13 Septembrie, Sector 5, Bucuresti": a date glued on
        out.append(Listing(
            source="publi24", source_id=url.group(1).rsplit("/", 1)[-1].removesuffix(".html"), url=url.group(1),
            title=title, description=_text(block, "article-description"),
            price_ron=_price(_text(block, "article-price"), eur_to_ron), city=city.split(",")[0].strip(),
            photos=[img.group(1)] if img else [], created_at=parse_date(_text(block, "article-date"), today),
        ))
    return out


def search(query: str, *, pages: int = 1, eur_to_ron: float = 5.0, get: Callable[[str], str] = _get) -> list[Listing]:
    out: list[Listing] = []
    for page in range(1, pages + 1):
        got = parse(get(SEARCH.format(q=urllib.parse.quote_plus(query), page=page)), eur_to_ron)
        out += got
        if len(got) < 15:
            break
    return out
