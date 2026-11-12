"""SQLite at ~/.flipperbot/flipperbot.db: every listing ever seen, its price
history, and what the bot decided about it. The listings are also the price
book: market value of a model = what the same model is listed for."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .models import Listing

SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    key TEXT PRIMARY KEY,
    source TEXT, source_id TEXT, url TEXT, title TEXT, description TEXT,
    price_ron INTEGER, currency TEXT, negotiable INTEGER,
    city TEXT, region TEXT, photos TEXT, created_at TEXT, refreshed_at TEXT,
    seller_id TEXT, seller_name TEXT, business INTEGER, delivery INTEGER,
    condition TEXT, category_id TEXT, params TEXT,
    first_seen TEXT, last_seen TEXT,
    brand TEXT, segment TEXT, model_key TEXT, refs TEXT, flags TEXT, lot_count INTEGER,
    tier TEXT, est_value_ron INTEGER, profit_ron INTEGER, reason TEXT,
    notified_tier TEXT, in_digest INTEGER DEFAULT 0,
    ai TEXT, ai_at TEXT
);
CREATE INDEX IF NOT EXISTS listings_model ON listings(model_key);
CREATE INDEX IF NOT EXISTS listings_tier ON listings(tier);
CREATE TABLE IF NOT EXISTS prices (key TEXT, price_ron INTEGER, seen_at TEXT);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""

TIER_RANK = {"bad": 0, "suspect": 1, "mid": 2, "good": 3, "real_good": 4}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        # Columns added after the first release: add them to older databases.
        have = {r["name"] for r in self.conn.execute("PRAGMA table_info(listings)")}
        for col in ("starred INTEGER DEFAULT 0", "hidden INTEGER DEFAULT 0", "niche TEXT DEFAULT 'watches'"):
            if col.split()[0] not in have:
                self.conn.execute(f"ALTER TABLE listings ADD COLUMN {col}")
        self.conn.commit()

    # -- listings ------------------------------------------------------------

    def get(self, key: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM listings WHERE key=?", (key,)).fetchone()

    def upsert(self, l: Listing) -> tuple[str, sqlite3.Row | None]:
        """Store a listing. Returns ('new' | 'price_drop' | 'price_up' | 'seen', previous row)."""
        prev = self.get(l.key)
        t = now()
        cols = dict(
            source=l.source, source_id=l.source_id, url=l.url, title=l.title, description=l.description,
            price_ron=l.price_ron, currency=l.currency, negotiable=int(l.negotiable), city=l.city,
            region=l.region, photos=json.dumps(l.photos), created_at=l.created_at,
            refreshed_at=l.refreshed_at, seller_id=l.seller_id, seller_name=l.seller_name,
            business=int(l.business), delivery=int(l.delivery), condition=l.condition,
            category_id=l.category_id, params=json.dumps(l.params, ensure_ascii=False), last_seen=t, niche=l.niche,
        )
        if prev is None:
            cols.update(key=l.key, first_seen=t)
            names = ", ".join(cols)
            self.conn.execute(f"INSERT INTO listings ({names}) VALUES ({', '.join('?' * len(cols))})", list(cols.values()))
            self.conn.execute("INSERT INTO prices VALUES (?,?,?)", (l.key, l.price_ron, t))
            change = "new"
        else:
            sets = ", ".join(f"{k}=?" for k in cols)
            self.conn.execute(f"UPDATE listings SET {sets} WHERE key=?", [*cols.values(), l.key])
            change = "seen"
            if l.price_ron and prev["price_ron"] and l.price_ron != prev["price_ron"]:
                self.conn.execute("INSERT INTO prices VALUES (?,?,?)", (l.key, l.price_ron, t))
                change = "price_drop" if l.price_ron < prev["price_ron"] else "price_up"
        self.conn.commit()
        return change, prev

    def set_verdict(self, key: str, ident: Any, verdict: Any) -> None:
        self.conn.execute(
            """UPDATE listings SET brand=?, segment=?, model_key=?, refs=?, flags=?, lot_count=?,
               tier=?, est_value_ron=?, profit_ron=?, reason=? WHERE key=?""",
            (
                ident.brand.name if ident.brand else None, ident.segment, ident.model_key,
                json.dumps(ident.refs), json.dumps(sorted(ident.flags)), ident.lot_count,
                verdict.tier, verdict.est_value_ron, verdict.profit_ron, verdict.reason, key,
            ),
        )
        self.conn.commit()

    def set_flag(self, key: str, flag: str, value: bool) -> None:
        assert flag in ("starred", "hidden")
        self.conn.execute(f"UPDATE listings SET {flag}=? WHERE key=?", (int(value), key))
        self.conn.commit()

    def mark_notified(self, key: str, tier: str) -> None:
        self.conn.execute("UPDATE listings SET notified_tier=? WHERE key=?", (tier, key))
        self.conn.commit()

    def set_ai(self, key: str, result: dict[str, Any]) -> None:
        self.conn.execute("UPDATE listings SET ai=?, ai_at=? WHERE key=?", (json.dumps(result, ensure_ascii=False), now(), key))
        self.conn.commit()

    def all(self) -> Iterable[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM listings").fetchall()

    def by_tier(self, tiers: list[str], *, since: str | None = None, limit: int = 50) -> list[sqlite3.Row]:
        q = f"SELECT * FROM listings WHERE tier IN ({','.join('?' * len(tiers))})"
        args: list[Any] = list(tiers)
        if since:
            q += " AND last_seen >= ?"
            args.append(since)
        q += " ORDER BY COALESCE(profit_ron, 0) DESC, last_seen DESC LIMIT ?"
        return self.conn.execute(q, [*args, limit]).fetchall()

    def undigested(self, tiers: list[str]) -> list[sqlite3.Row]:
        q = f"SELECT * FROM listings WHERE in_digest=0 AND tier IN ({','.join('?' * len(tiers))}) ORDER BY COALESCE(profit_ron,0) DESC"
        return self.conn.execute(q, tiers).fetchall()

    def mark_digested(self, keys: list[str]) -> None:
        self.conn.executemany("UPDATE listings SET in_digest=1 WHERE key=?", [(k,) for k in keys])
        self.conn.commit()

    # -- price book ------------------------------------------------------------

    def comparable_prices(self, model_key: str, exclude_key: str | None = None, days: int = 365) -> list[int]:
        """Asking prices of working, single, real items of this model."""
        rows = self.conn.execute(
            """SELECT key, price_ron, flags FROM listings
               WHERE model_key=? AND price_ron IS NOT NULL AND price_ron > 0
               AND last_seen >= datetime('now', ?)""",
            (model_key, f"-{days} days"),
        ).fetchall()
        bad = {"broken", "lot", "replica", "part", "wanted", "service", "battery"}
        out = []
        for r in rows:
            if r["key"] == exclude_key:
                continue
            if bad & set(json.loads(r["flags"] or "[]")):
                continue
            out.append(r["price_ron"])
        return out

    # -- key/value ---------------------------------------------------------------

    def kv_get(self, k: str, default: Any = None) -> Any:
        row = self.conn.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        return json.loads(row["v"]) if row else default

    def kv_set(self, k: str, v: Any) -> None:
        self.conn.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", (k, json.dumps(v)))
        self.conn.commit()
