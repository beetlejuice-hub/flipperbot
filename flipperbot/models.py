from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Listing:
    """One marketplace listing, the same shape whatever site it came from."""

    source: str  # "olx", "facebook", ...
    source_id: str
    url: str
    title: str
    description: str = ""
    price: float | None = None  # in `currency`
    currency: str = "RON"
    price_ron: int | None = None
    negotiable: bool = False
    previous_price_ron: int | None = None  # the site's own "price dropped from"
    city: str = ""
    region: str = ""
    photos: list[str] = field(default_factory=list)
    created_at: str = ""
    refreshed_at: str = ""
    seller_id: str = ""
    seller_name: str = ""
    business: bool = False
    delivery: bool = False
    condition: str = ""  # "used", "new", "damaged" when the site says
    category_id: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.source_id}"
