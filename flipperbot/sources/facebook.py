"""Facebook Marketplace, through danyk20's facebook-marketplace-scraper
(github.com/danyk20/facebook-marketplace-scraper): a real Chromium browser on
your Mac, logged in once by hand with your SECOND Facebook account, its
session kept in ~/.flipperbot/facebook-profile.

The browser is your real Google Chrome when installed (in its own profile), else Chromium.
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
from contextlib import contextmanager
from pathlib import Path
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
# The browser: your real Google Chrome when it's installed (steady, and what Facebook sees every
# day), in its own profile at ~/.flipperbot/facebook-profile, so your normal Chrome is untouched.
# Without Chrome, the toolkit's own Chromium.

CHROME_APPS = [Path("/Applications/Google Chrome.app"), Path.home() / "Applications" / "Google Chrome.app"]
_CHANNEL_FILE = "flipperbot-channel.txt"


def channel() -> str:
    """'chrome' or '' (bundled Chromium). Fixed at the first login: the profile has to be reopened
    by the same browser it was made with, or the saved login can't be read back."""
    saved = PROFILE / _CHANNEL_FILE
    if saved.exists():
        return saved.read_text().strip()
    return "chrome" if any(p.exists() for p in CHROME_APPS) else ""


@contextmanager
def session(headless: bool) -> Iterator[Any]:
    from playwright.sync_api import sync_playwright

    browser, _, _ = _lib()
    PROFILE.mkdir(parents=True, exist_ok=True)
    options: dict[str, Any] = {
        "headless": headless, "viewport": {"width": 1300, "height": 950},
        "locale": "ro-RO", "timezone_id": "Europe/Bucharest",
    }
    if headless:
        options["user_agent"] = browser.USER_AGENT  # same as the library: headless Chrome names itself in its UA
    if channel():
        options["channel"] = channel()
    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(str(PROFILE), **options)
        try:
            yield ctx
        finally:
            try:
                ctx.close()
            except Exception:
                pass


def logged_in(ctx: Any) -> bool:
    """Facebook sets the c_user cookie once you're logged in."""
    try:
        return any(c.get("name") == "c_user" for c in ctx.cookies("https://www.facebook.com"))
    except Exception:
        return False


def _page(ctx: Any) -> Any:
    return ctx.pages[-1] if ctx.pages else ctx.new_page()


# --------------------------------------------------------------------------
# Login, once, by hand


def login(wait_minutes: int = 15) -> None:
    """Open a Chrome window on Facebook's login page and wait (no Enter needed) until you're logged
    in with the second account. Then let you clear any Marketplace consent screen, and set the
    account's Marketplace radius to 500 km around Bucharest."""
    _, _, scraper = _lib()
    which = "Google Chrome" if channel() == "chrome" else "a Chromium browser window"
    print(f"Opening {which} on Facebook (a separate profile: your normal Chrome isn't touched).")
    print("Log in there with your SECOND Facebook account (never your main one), including any code")
    print("Facebook asks for. Don't close that window: this continues by itself once you're in.\n")
    with session(headless=False) as ctx:
        page = _page(ctx)
        if not logged_in(ctx):
            page.goto("https://www.facebook.com/login", wait_until="domcontentloaded")
            deadline = time.time() + wait_minutes * 60
            while not logged_in(ctx):
                if time.time() > deadline:
                    raise NotLoggedIn(f"Not logged in after {wait_minutes} minutes. Run `flipperbot facebook-login` again.")
                if not ctx.pages:  # window closed by hand: open the login page again
                    _page(ctx).goto("https://www.facebook.com/login", wait_until="domcontentloaded")
                time.sleep(2)
        print("✓ Logged in.")
        (PROFILE / _CHANNEL_FILE).write_text(channel())
        page = _page(ctx)
        page.goto(scraper.build_search_url("ceas", COUNTRY), wait_until="domcontentloaded")
        print("\nThe window now shows Marketplace. If Facebook asks about Marketplace or how your data is")
        print("used, accept it there. When you see watch listings, come back here.")
        input("Press Enter: ")
        try:
            scraper.set_account_search_radius(_page(ctx), ANCHOR["radius_km"], "ceas", country=COUNTRY, verbose=False)
            print("Search area set: 500 km around Bucharest (covers most of Romania).")
        except Exception as e:  # the account still works with whatever radius it has
            print(f"Couldn't set the search radius by itself ({type(e).__name__}).")
            print("In that window: click the location at the top of Marketplace → Bucharest, radius 500 km, Apply.")
            input("Press Enter when done: ")
    print("Facebook is set up. The bot uses this login from now on, in the background.")


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
    _, _, scraper = _lib()
    with session(headless=True) as ctx:
        if not logged_in(ctx):
            raise NotLoggedIn("no Facebook login saved, or it expired")
        page = _page(ctx)
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
