"""Facebook Marketplace, through danyk20's facebook-marketplace-scraper
(github.com/danyk20/facebook-marketplace-scraper): a real Chromium browser on
your Mac, logged in once by hand with your SECOND Facebook account, its
session kept in ~/.flipperbot/facebook-profile.

Why a browser: Facebook blocks plain requests and hides Marketplace search
behind a login. Why slow: a logged-in account that searches too often gets
checkpointed, so the bot does a couple of searches every 30-60 minutes and
opens only new listings that look like watches.

The library ships Switzerland only; Romania is added here as an anchor city
(Bucharest) with Facebook's largest radius, 500 km, set on the account once
at login. Facebook's search for a logged-in account uses that saved radius.

Everything here needs Facebook and a human-logged-in account, so it can't be
tested from a server: tests cover the parts that don't touch Facebook.
"""

from __future__ import annotations

import os
import random
import re
import time
from typing import Any, Callable, Iterator

from ..config import HOME
from ..models import Listing

PROFILE = HOME / "facebook-profile"
COUNTRY = "ro"
ANCHOR = {"slug": "bucharest", "radius_km": 500, "bounds": (43.6, 48.3, 20.2, 29.8)}
QUERIES = [
    "ceas", "ceasuri", "lot ceasuri", "ceas automatic", "ceas mecanic", "ceas vechi", "ceas defect",
    "ceas sovietic", "omega", "seiko", "tissot", "longines", "rolex", "poljot", "orient", "citizen",
]


class NotLoggedIn(RuntimeError):
    """The saved session is gone (logged out, checkpoint, consent screen): needs `flipperbot facebook-login`."""


def installed() -> bool:
    try:
        import fb_scraper  # noqa: F401
        import playwright  # noqa: F401
    except ImportError:
        return False
    return True


def _lib() -> tuple[Any, Any, Any]:
    """Import the library with its browser profile pointed at ours, and Romania registered."""
    os.environ.setdefault("FB_SCRAPER_PROFILE_DIR", str(PROFILE))
    from fb_scraper import browser, config, scraper

    config.COUNTRY_ANCHORS.setdefault(COUNTRY, ANCHOR)  # type: ignore[arg-type]
    return browser, config, scraper


# --------------------------------------------------------------------------
# Prices: Facebook shows them as rendered text, e.g. "1.200 lei", "RON1,200", "€300", "Gratuit"

_NUM = re.compile(r"\d[\d.,'\s\u00a0\u202f]*\d|\d")
_GROUPED = re.compile(r"^\d{1,3}(?:[.,'\s\u00a0\u202f]\d{3})+(?:[.,]\d{1,2})?$")  # 1.200 / 1,200.00 / 12 500


def parse_price(text: str | None, eur_to_ron: float = 5.0) -> int | None:
    """Lei from Facebook's rendered price. None for free, unknown currencies, or no number."""
    if not text:
        return None
    t = text.lower()
    m = _NUM.search(t)
    if not m:
        return None
    num = m.group(0)
    if _GROUPED.match(num):
        num = re.sub(r"[.,]\d{1,2}$", "", num) if re.search(r"[.,]\d{1,2}$", num) and not re.search(r"[.,]\d{3}$", num) else num
        value = int(re.sub(r"\D", "", num))
    elif re.fullmatch(r"\d+[.,]\d{1,2}", num):
        value = round(float(num.replace(",", ".")))
    else:
        value = int(re.sub(r"\D", "", num))
    rest = t.replace(m.group(0), " ")
    if "€" in rest or "eur" in rest:
        value = round(value * eur_to_ron)
    elif not ("lei" in rest or "ron" in rest or not re.search(r"[^\s\d]", rest)):
        return None  # another currency: skip rather than misprice
    return value or None


def to_listing(item: dict[str, Any], eur_to_ron: float = 5.0) -> Listing | None:
    lid = item.get("listing_id")
    if not lid:
        return None
    images = item.get("images") or ([item["image_url"]] if item.get("image_url") else [])
    location = item.get("location") or ""
    return Listing(
        source="facebook",
        source_id=str(lid),
        url=item.get("url") or f"https://www.facebook.com/marketplace/item/{lid}/",
        title=(item.get("title") or "").strip(),
        description=item.get("description") or "",
        price_ron=parse_price(item.get("price"), eur_to_ron),
        previous_price_ron=parse_price(item.get("original_price"), eur_to_ron),
        city=location.split(",")[0].strip(),
        region=location.split(",")[-1].strip() if "," in location else "",
        photos=list(images),
        seller_name=item.get("seller_name") or "",
        seller_id=item.get("seller_profile_url") or "",
        condition=item.get("condition") or "",
        params={"posted": item.get("posted_at")} if item.get("posted_at") else {},
    )


# --------------------------------------------------------------------------
# Login, once, by hand


def login() -> None:
    """Open a real browser window to log in with the second account, clear Facebook's consent
    screen if it shows, and set the account's Marketplace radius to 500 km around Bucharest."""
    browser, _, scraper = _lib()
    print("A browser window will open on Facebook.")
    print("Log in with your SECOND Facebook account (never your main one). If Facebook shows a")
    print("Marketplace consent or data screen, accept it. Then come back here and press Enter.\n")
    with browser.FacebookSession(headless=False) as ctx:
        page = ctx.new_page()
        page.goto(scraper.build_search_url("ceas", COUNTRY), wait_until="domcontentloaded")
        input("Logged in and you can see Marketplace results? Press Enter: ")
        if not browser.is_logged_in(page):
            raise NotLoggedIn("Still not logged in. Run `flipperbot facebook-login` again.")
        try:
            scraper.set_account_search_radius(page, ANCHOR["radius_km"], "ceas", country=COUNTRY, verbose=False)
            print("Search area set: 500 km around Bucharest (covers most of Romania).")
        except Exception as e:  # the account still works with whatever radius it has
            print(f"Couldn't set the search radius by itself ({type(e).__name__}).")
            print("In that window: Marketplace → Location → Bucharest, radius 500 km, then Apply.")
            input("Press Enter when done: ")
    print("Facebook is set up. The bot uses this login from now on.")


# --------------------------------------------------------------------------
# Searching


def search(
    queries: list[str],
    *,
    is_new: Callable[[str], bool],
    looks_like_watch: Callable[[Listing], bool],
    max_details: int = 8,
    eur_to_ron: float = 5.0,
    pause: tuple[float, float] = (4.0, 10.0),
    log: Callable[[str], None] = print,
) -> Iterator[Listing]:
    """Search each query (newest first, a few scrolls), then open the new watch-looking
    listings for description and photos. Raises NotLoggedIn when the session is gone."""
    browser, _, scraper = _lib()
    with browser.FacebookSession(headless=True) as ctx:
        page = ctx.new_page()
        details_left = max_details
        for i, q in enumerate(queries):
            if i:
                time.sleep(random.uniform(*pause))
            try:
                items = scraper.search_listings(page, q, COUNTRY, max_scrolls=3, verbose=False)
            except (scraper.LoginRequiredError, scraper.MarketplaceConsentRequiredError) as e:
                raise NotLoggedIn(str(e)) from e
            log(f"  facebook {q!r}: {len(items)}")
            for item in items:
                l = to_listing(item, eur_to_ron)
                if l is None:
                    continue
                if details_left > 0 and is_new(l.key) and looks_like_watch(l):
                    time.sleep(random.uniform(*pause))
                    try:
                        detail = scraper.fetch_detail(page, l.source_id, fetch_seller_listings=False)
                        l = to_listing({**item, **{k: v for k, v in detail.items() if v}}, eur_to_ron) or l
                    except (scraper.LoginRequiredError, scraper.MarketplaceConsentRequiredError) as e:
                        raise NotLoggedIn(str(e)) from e
                    except Exception as e:  # one broken listing page shouldn't stop the run
                        log(f"  facebook detail failed for {l.source_id}: {type(e).__name__}")
                    details_left -= 1
                yield l
