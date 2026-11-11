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

# Repair cost to assume for a "broken" watch, by segment (lei). A dead battery
# is its own, much cheaper case (`battery_fix_ron`).
REPAIR_RON = {"japan": 250, "soviet": 200, "swiss": 600, "vintage": 500, "luxury": 1500}


@dataclass
class Settings:
    # Polling
    poll_every_min: tuple[int, int] = (5, 10)  # random wait between polls
    searches_per_poll: int = 3  # random terms from the pool, plus the watch category feeds
    pause_between_requests_s: tuple[float, float] = (3.0, 8.0)
    blocked_backoff_min: int = 60
    search_pool: list[str] = field(default_factory=lambda: list(SEARCH_POOL))
    eur_to_ron: float = 5.0

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

    # AI (Claude Code on this machine, on your subscription)
    ai_enabled: bool = True
    ai_daily_limit: int = 15  # a $20 plan runs out fast; raise it if you never hit limits
    ai_tiers: list[str] = field(default_factory=lambda: ["real_good", "good"])
    ai_timeout_s: int = 420
    claude_bin: str = "claude"

    # Telegram
    telegram_token: str = ""
    telegram_chat_id: str = ""
    alert_tiers: list[str] = field(default_factory=lambda: ["real_good", "good"])

    @property
    def db_path(self) -> Path:
        return HOME / "flipperbot.db"

    @property
    def photos_dir(self) -> Path:
        return HOME / "photos"


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
