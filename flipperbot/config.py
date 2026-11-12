"""Settings. Defaults live here; your own values go in ~/.flipperbot/config.toml
(copy config.example.toml). Only what you put in the file overrides a default."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

HOME = Path(os.environ.get("FLIPPERBOT_HOME") or Path.home() / ".flipperbot")

# What to search for. Each poll takes a few of these at random, so the bot
# doesn't hit OLX with the same requests every time and covers more ground.
SEARCH_POOL = [
    # generic
    "ceas", "ceasuri", "ceas barbatesc", "ceas automatic", "ceas mecanic", "ceas vechi",
    "ceasuri vechi", "ceas vintage", "ceas de colectie", "ceas elvetian", "ceas de buzunar",
    # lots and broken
    "lot ceasuri", "ceasuri lot", "colectie ceasuri", "ceas defect", "ceas pentru piese",
    "ceasuri defecte", "ceas nefunctional",
    # soviet
    "ceas sovietic", "ceas rusesc", "poljot", "vostok", "raketa", "pobeda", "slava",
    # brands
    "seiko", "orient", "citizen", "casio", "tissot", "hamilton", "longines", "omega",
    "rolex", "tag heuer", "oris", "rado", "certina", "mido", "tudor", "zenith", "heuer",
    "doxa", "enicar", "eterna", "zodiac", "universal geneve", "breitling", "cartier",
    # gold
    "ceas aur",
]

# Where sellers often don't know what they have: lots, old and inherited watches. Most polls
# include some of these (`focus_share`).
FOCUS_POOL = [
    "lot ceasuri", "lot ceasuri vechi", "ceasuri vechi", "ceas vechi", "ceas de mana vechi", "ceas antic",
    "ceasul bunicului", "ceas bunic", "ceas mostenire", "ceasuri din pod", "vechituri", "obiecte vechi ceas",
    "ceas mecanic vechi", "ceasuri mecanice vechi", "ceas de buzunar", "ceas de buzunar argint", "ceas aur vechi",
    "ceasuri defecte", "lot ceasuri defecte", "ceasuri pentru piese", "ceas sovietic", "ceasuri sovietice lot",
    "ceas militar", "ceas elvetian vechi", "ceasuri de colectie", "colectie ceasuri vechi",
]

# Modern watches that resell easily: clear model numbers, so the price book prices them well.
MODERN_POOL = [
    "seiko 5 sports", "seiko presage", "seiko prospex", "seiko srpd", "seiko turtle", "seiko samurai",
    "orient bambino", "orient kamasu", "orient star", "casio g-shock", "g-shock ga-2100", "casio gw-m5610",
    "casio oceanus", "casio edifice", "citizen promaster", "citizen tsuyosa", "citizen eco-drive",
    "tissot prx", "tissot seastar", "tissot le locle", "hamilton khaki", "hamilton jazzmaster",
    "longines hydroconquest", "longines conquest", "certina ds", "mido ocean star", "oris aquis",
    "seiko automatic", "ceas automatic nou", "ceas sigilat",
    "apple watch", "apple watch ultra", "apple watch series", "garmin fenix", "garmin forerunner", "garmin venu",
    "garmin instinct", "galaxy watch", "pixel watch", "huawei watch gt", "amazfit", "suunto", "smartwatch",
]

MAX_LISTING_AGE_DAYS = 30

# Repair cost to assume for a "broken" watch, by segment (lei). A dead battery
# is its own, much cheaper case (`battery_fix_ron`).
REPAIR_RON = {"japan": 250, "soviet": 200, "swiss": 600, "vintage": 500, "luxury": 1500, "smart": 200}


@dataclass
class Settings:
    # Polling
    poll_every_min: tuple[int, int] = (5, 10)  # random wait between polls
    searches_per_poll: int = 3  # random terms from the pool, plus the watch category feeds
    # OLX's "newest" order is by last paid refresh, so most of page 1 is old listings bumped back up;
    # 3 pages per watch category catch everything newly posted between two polls.
    feed_pages: int = 3
    pause_between_requests_s: tuple[float, float] = (3.0, 8.0)
    blocked_backoff_min: int = 60
    niches: list[str] = field(default_factory=lambda: ["watches"])  # what to hunt (see niches.py)
    search_pool: list[str] = field(default_factory=lambda: list(SEARCH_POOL))
    focus_pool: list[str] = field(default_factory=lambda: list(FOCUS_POOL))
    modern_pool: list[str] = field(default_factory=lambda: list(MODERN_POOL))
    # Each poll's random searches: about a third lots/old (focus_pool), a third modern, the rest general.
    focus_share: float = 0.34
    modern_share: float = 0.33
    eur_to_ron: float = 5.0

    # Facebook Marketplace (needs `flipperbot facebook-login` once, with a second account)
    facebook_every_min: tuple[int, int] = (30, 60)  # slow on purpose: a busy account gets checkpointed
    facebook_searches_per_run: int = 2
    facebook_max_details: int = 8  # new watch-looking listings opened per run for description + photos

    # Money
    budget_ron: int = 5000  # skip anything above what you'd pay
    resale_haircut: float = 0.85  # listings ask more than things sell for
    battery_fix_ron: int = 40
    repair_ron: dict[str, int] = field(default_factory=lambda: dict(REPAIR_RON))

    # Tiers: discount = how far under the market price; profit in lei after repair
    real_good_discount: float = 0.50
    real_good_profit_ron: int = 300
    good_discount: float = 0.30
    good_profit_ron: int = 150
    mid_discount: float = 0.15
    min_comps: int = 4  # listings of the same model needed to trust a market price

    # AI (Claude Code on this machine, on your subscription). Claude only checks what you send it
    # from the dashboard ("Send to Claude"). ai_auto = true lets the bot send real good deals, lots and
    # old watches to Claude by itself, and message Telegram when Claude confirms one.
    ai_enabled: bool = True
    ai_auto: bool = False
    # Real good deals only: the bot has Claude check them by itself (fake or not, realistic price), in the
    # background on your subscription, no Claude window needed; confirmed ones go to Telegram. Counts
    # toward ai_daily_limit. Everything else waits for "Send to Claude".
    ai_auto_real_good: bool = True
    ai_daily_limit: int = 15  # a $20 plan runs out fast; raise it if you never hit limits
    # Claude looks at every real_good before it's sent to Telegram, then at good ones with what's left
    # of the day's budget (those only show on the dashboard).
    ai_tiers: list[str] = field(default_factory=lambda: ["real_good", "good"])
    ai_timeout_s: int = 420
    # Sonnet is far lighter on a Claude plan's usage limit than Opus and plenty for this.
    ai_model: str = "sonnet"
    ai_max_photos: int = 5  # per single watch; lots get 8 plus zoomed quarters of the first 3
    claude_bin: str = "claude"

    # Dashboard (http://localhost:8789; if another app has that port, the next free one:
    # `flipperbot open` always finds it). dashboard_lan = true also serves it to your phone
    # on the same Wi-Fi, at http://<your-mac-name>.local:<port> (anyone on that Wi-Fi can see it).
    dashboard_port: int = 8789
    dashboard_lan: bool = False

    # eBay (official Browse API, free keys from developer.ebay.com: `flipperbot ebay-setup`)
    ebay_client_id: str = ""
    ebay_client_secret: str = ""
    ebay_daily_calls: int = 300

    # Telegram
    telegram_token: str = ""
    telegram_chat_id: str = ""
    alert_tiers: list[str] = field(default_factory=lambda: ["real_good"])  # Telegram; the rest is on the dashboard
    # Telegram only gets a real_good deal once Claude has confirmed it: not likely fake, verdict buy or
    # negotiate, and at least this sure (0-100). Unchecked or unconfirmed deals stay on the dashboard.
    # Good deals go fast. A listing up longer than this (OLX's own creation date, not its paid "refresh")
    # can't be a deal: it tops out at "maybe". Unless its price was cut in the last two weeks.
    max_listing_age_days: int = MAX_LISTING_AGE_DAYS
    alert_min_confidence: int = 50
    alert_min_confidence_luxury: int = 60  # luxury/Swiss: most cheap ones in Romania are replicas
    digest_telegram: bool = False  # the 20:00 summary of mids on Telegram (they're on the dashboard anyway)

    @property
    def db_path(self) -> Path:
        return HOME / "flipperbot.db"

    @property
    def photos_dir(self) -> Path:
        return HOME / "photos"


def set_value(key: str, value: str, path: Path | None = None) -> None:
    """Write `key = "value"` into the config file, replacing the line if it's there."""
    import re

    path = path or HOME / "config.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text() if path.exists() else (Path(__file__).parent / "config.example.toml").read_text()
    line = f'{key} = "{value}"'
    pattern = re.compile(rf"^{re.escape(key)}\s*=.*$", re.M)
    text = pattern.sub(lambda m: line, text, count=1) if pattern.search(text) else text.rstrip() + "\n" + line + "\n"
    path.write_text(text)


def load(path: Path | None = None) -> Settings:
    path = path or HOME / "config.toml"
    s = Settings()
    if path.exists():
        data = tomllib.loads(path.read_text())
        flat: dict = {}
        for k, v in data.items():
            if isinstance(v, dict) and k not in ("repair_ron",):
                flat.update(v)  # allow [telegram], [tiers] sections
            else:
                flat[k] = v
        names = {f.name for f in fields(Settings)}
        for k, v in flat.items():
            if k in names:
                cur = getattr(s, k)
                setattr(s, k, tuple(v) if isinstance(cur, tuple) else v)
    s.telegram_token = os.environ.get("FLIPPERBOT_TELEGRAM_TOKEN", s.telegram_token)
    s.telegram_chat_id = os.environ.get("FLIPPERBOT_TELEGRAM_CHAT_ID", s.telegram_chat_id)
    return s
