"""SQLite at ~/.flipperbot/flipperbot.db: every listing ever seen, its price
history, and what the bot decided about it. The listings are also the price
book: market value of a model = what the same model is listed for."""

from __future__ import annotations

import json
import re
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
-- What Claude found an ordinary used, working one of a model sells for (sold prices): it overrides the
-- estimate from asking prices for every listing of that model.
-- What you bought and sold: the bot learns real prices and which categories make money from it.
CREATE TABLE IF NOT EXISTS deals (key TEXT PRIMARY KEY, bought_price INTEGER, bought_at TEXT, sold_price INTEGER,
                                  sold_at TEXT, costs INTEGER DEFAULT 0, note TEXT);
CREATE TABLE IF NOT EXISTS model_prices (model_key TEXT PRIMARY KEY, low INTEGER, high INTEGER, at TEXT,
                                         from_key TEXT, note TEXT);
"""

TIER_RANK = {"bad": 0, "suspect": 1, "mid": 2, "good": 3, "real_good": 4}


def _days_between(a: str | None, b: str | None) -> float:
    try:
        x = datetime.fromisoformat((a or "").replace("Z", "+00:00"))
        y = datetime.fromisoformat((b or "").replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    # SQLite's datetime('now') has no zone and is UTC; OLX's times carry one: treat the zoneless as UTC
    if x.tzinfo is None:
        x = x.replace(tzinfo=timezone.utc)
    if y.tzinfo is None:
        y = y.replace(tzinfo=timezone.utc)
    return (y - x).total_seconds() / 86400


def _title_words(title: str | None) -> set[str]:
    from .identify import normalize

    return {w for w in re.split(r"[^a-z0-9]+", normalize(title or "")) if len(w) > 2 and w not in ("vand", "vind", "urgent")}


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
        for col in ("starred INTEGER DEFAULT 0", "hidden INTEGER DEFAULT 0", "niche TEXT DEFAULT 'watches'",
                    "triage TEXT", "est_high_ron INTEGER", "ebay TEXT", "liquidity TEXT",
                    # the 0-10 score: free rules, the quick AI read, and the final one
                    "rule_score INTEGER", "rule_why TEXT", "quick TEXT", "quick_at TEXT", "score INTEGER", "score_why TEXT",
                    # OLX bumps ("reactualizare") and reposts: how often it was pushed back to the top, and the
                    # first time this item was posted if the seller deleted and posted it again
                    "bumps INTEGER DEFAULT 0", "orig_created_at TEXT", "repost_of TEXT",
                    # gone from OLX: when we found out, and why (sold / expired / reposted)
                    "gone_at TEXT", "gone_reason TEXT", "alive_checked_at TEXT",
                    # the price as the seller wrote it (e.g. 450 in EUR), next to price_ron
                    "price_orig REAL"):  # your call on an Interesting listing: claude / skip / fake
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
            price_ron=l.price_ron, price_orig=l.price, currency=l.currency, negotiable=int(l.negotiable), city=l.city,
            region=l.region, photos=json.dumps(l.photos), created_at=l.created_at,
            refreshed_at=l.refreshed_at, seller_id=l.seller_id, seller_name=l.seller_name,
            business=int(l.business), delivery=int(l.delivery), condition=l.condition,
            category_id=l.category_id, params=json.dumps(l.params, ensure_ascii=False), last_seen=t, niche=l.niche,
        )
        if prev is None:
            # Seen for the first time but refreshed well after it was posted: it was bumped before we saw it.
            cols.update(key=l.key, first_seen=t, bumps=int(_days_between(l.created_at, l.refreshed_at) >= 1))
            origin = self.find_repost(l)
            if origin is not None:
                cols.update(repost_of=origin["key"],
                            orig_created_at=min(x for x in (origin["orig_created_at"], origin["created_at"], l.created_at) if x))
            names = ", ".join(cols)
            self.conn.execute(f"INSERT INTO listings ({names}) VALUES ({', '.join('?' * len(cols))})", list(cols.values()))
            self.conn.execute("INSERT INTO prices VALUES (?,?,?)", (l.key, l.price_ron, t))
            change = "new"
        else:
            sets = ", ".join(f"{k}=?" for k in cols)
            self.conn.execute(f"UPDATE listings SET {sets} WHERE key=?", [*cols.values(), l.key])
            change = "seen"
            if l.refreshed_at and prev["refreshed_at"] and l.refreshed_at > prev["refreshed_at"]:
                # OLX "reactualizare": the same listing pushed back to the top, not a new one
                self.conn.execute("UPDATE listings SET bumps = COALESCE(bumps, 0) + 1 WHERE key=?", (l.key,))
                change = "bumped"
            if l.price_ron and prev["price_ron"] and l.price_ron != prev["price_ron"]:
                self.conn.execute("INSERT INTO prices VALUES (?,?,?)", (l.key, l.price_ron, t))
                change = "price_drop" if l.price_ron < prev["price_ron"] else "price_up"
        self.conn.commit()
        return change, prev

    def find_repost(self, l: Listing) -> sqlite3.Row | None:
        """The same seller's earlier listing of the same item, now gone: a delete-and-post-again to look new.
        Same seller, nearly the same title, a price within 25%, and the old one not seen for 2+ days (several
        identical listings that are all still up are a shop's stock, not a repost)."""
        if not l.seller_id or not l.title:
            return None
        words = _title_words(l.title)
        if len(words) < 2:
            return None
        rows = self.conn.execute(
            """SELECT * FROM listings WHERE source=? AND seller_id=? AND key!=? AND last_seen < datetime('now', '-2 days')
               ORDER BY COALESCE(orig_created_at, created_at, first_seen) LIMIT 200""",
            (l.source, l.seller_id, l.key)).fetchall()
        for r in rows:
            other = _title_words(r["title"])
            same = len(words & other) / max(1, len(words | other))
            close = not (l.price_ron and r["price_ron"]) or abs(l.price_ron - r["price_ron"]) <= 0.25 * max(l.price_ron, r["price_ron"])
            if same >= 0.7 and close:
                return r
        return None

    def set_verdict(self, key: str, ident: Any, verdict: Any) -> None:
        self.conn.execute(
            """UPDATE listings SET brand=?, segment=?, model_key=?, refs=?, flags=?, lot_count=?,
               tier=?, est_value_ron=?, profit_ron=?, reason=?, est_high_ron=? WHERE key=?""",
            (
                ident.brand.name if ident.brand else None, ident.segment, ident.model_key,
                json.dumps(ident.refs), json.dumps(sorted(ident.flags)), ident.lot_count,
                verdict.tier, verdict.est_value_ron, verdict.profit_ron, verdict.reason,
                getattr(verdict, "est_high_ron", None), key,
            ),
        )
        self.conn.commit()

    def update_score(self, key: str) -> None:
        """Recompute the final 0-10 score from what's known now (rules, quick AI, full Claude check)."""
        from .scoring import final_score

        row = self.get(key)
        if row is None:
            return
        score, why = final_score(row)
        self.conn.execute("UPDATE listings SET score=?, score_why=? WHERE key=?", (score, why, key))
        self.conn.commit()

    def set_triage(self, key: str, triage: str | None) -> None:
        self.conn.execute("UPDATE listings SET triage=? WHERE key=?", (triage, key))
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
        self.learn_model_price(key, result)
        self.update_score(key)

    def learn_model_price(self, key: str, result: dict[str, Any]) -> bool:
        """Claude priced an ordinary one of this exact model: remember it for the model's other listings."""
        row = self.get(key)
        try:
            lo, hi = int(result.get("model_value_ron_low") or 0), int(result.get("model_value_ron_high") or 0)
        except (TypeError, ValueError):
            return False
        if (row is None or "|" not in (row["model_key"] or "") or lo <= 0 or hi < lo or "error" in result
                or result.get("authenticity") == "likely_fake" or "lot" in (row["flags"] or "")):
            return False
        self.conn.execute("INSERT OR REPLACE INTO model_prices VALUES (?, ?, ?, ?, ?, ?)",
                          (row["model_key"], lo, hi, now(), key, str(result.get("price_note") or "")[:200]))
        self.conn.commit()
        return True

    def model_price(self, model_key: str | None, days: int = 120) -> tuple[int, int] | None:
        """Claude's checked price for this model, if recent."""
        if not model_key:
            return None
        r = self.conn.execute("SELECT low, high FROM model_prices WHERE model_key=? AND at >= datetime('now', ?)",
                              (model_key, f"-{days} days")).fetchone()
        return (r["low"], r["high"]) if r else None

    def set_quick(self, key: str, quick: dict[str, Any]) -> None:
        self.conn.execute("UPDATE listings SET quick=?, quick_at=? WHERE key=?", (json.dumps(quick, ensure_ascii=False), now(), key))
        self.conn.commit()
        self.update_score(key)

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

    # -- your own flips ------------------------------------------------------------
    def set_bought(self, key: str, price: int, note: str = "") -> None:
        self.conn.execute("""INSERT INTO deals (key, bought_price, bought_at, note) VALUES (?, ?, ?, ?)
                             ON CONFLICT(key) DO UPDATE SET bought_price=excluded.bought_price, note=excluded.note""",
                          (key, price, now(), note))
        self.conn.commit()

    def set_resold(self, key: str, price: int, costs: int = 0) -> None:
        self.conn.execute("UPDATE deals SET sold_price=?, sold_at=?, costs=? WHERE key=?", (price, now(), costs, key))
        self.conn.commit()

    def forget_deal(self, key: str) -> None:
        self.conn.execute("DELETE FROM deals WHERE key=?", (key,))
        self.conn.commit()

    def deal(self, key: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM deals WHERE key=?", (key,)).fetchone()

    def flips(self) -> dict[str, Any]:
        """What you bought and sold: totals, by category, and each flip."""
        rows = self.conn.execute(
            """SELECT d.*, l.title, l.url, l.niche, l.model_key, l.est_value_ron, l.est_high_ron, l.price_ron AS asked
               FROM deals d LEFT JOIN listings l ON l.key = d.key ORDER BY d.bought_at DESC""").fetchall()
        items, cats = [], {}
        for r in rows:
            profit = (r["sold_price"] - r["bought_price"] - (r["costs"] or 0)) if r["sold_price"] is not None else None
            days = round(_days_between(r["bought_at"], r["sold_at"])) if r["sold_at"] else None
            items.append({**dict(r), "profit": profit, "days": days})
            c = cats.setdefault(r["niche"] or "?", {"bought": 0, "sold": 0, "spent": 0, "got": 0, "profit": 0, "days": []})
            c["bought"] += 1
            c["spent"] += r["bought_price"] or 0
            if profit is not None:
                c["sold"] += 1
                c["got"] += r["sold_price"]
                c["profit"] += profit
                c["days"].append(days or 0)
        for c in cats.values():
            d = sorted(c.pop("days"))
            c["median_days"] = d[len(d) // 2] if d else None
        sold = [i for i in items if i["profit"] is not None]
        return {"items": items, "by_category": cats,
                "total": {"bought": len(items), "sold": len(sold), "profit": sum(i["profit"] for i in sold),
                          "in_stock": sum(i["bought_price"] or 0 for i in items if i["profit"] is None)}}

    def sold(self, model_key: str | None, days: int = 120, used_only: bool = False) -> list[tuple[int, float]]:
        """Listings of this model that disappeared as sold (not expired, not reposted) lately: (last price, days it was up)."""
        if not model_key or "|" not in model_key:
            return []
        rows = self.conn.execute(
            f"""SELECT price_ron, gone_at, COALESCE(orig_created_at, NULLIF(created_at, ''), first_seen) AS since, flags
               FROM listings WHERE model_key=? AND gone_reason='sold' AND price_ron > 0 AND gone_at >= datetime('now', ?)
               {"AND COALESCE(business, 0) = 0" if used_only else ""}""",
            (model_key, f"-{days} days")).fetchall()
        bad = {"broken", "lot", "replica", "part", "wanted", "service", "battery"} | ({"new"} if used_only else set())
        out = [(r["price_ron"], max(0.0, _days_between(r["since"], r["gone_at"]))) for r in rows
               if not bad & set(json.loads(r["flags"] or "[]"))]
        # Your own resales of this model: the truest price there is (twice, to weigh more than a guess).
        for r in self.conn.execute("""SELECT d.sold_price, d.bought_at, d.sold_at FROM deals d JOIN listings l ON l.key = d.key
                                      WHERE l.model_key = ? AND d.sold_price > 0 AND d.sold_at >= datetime('now', ?)""",
                                   (model_key, f"-{days} days")):
            out += [(r["sold_price"], max(0.0, _days_between(r["bought_at"], r["sold_at"])))] * 2
        return out

    def comparable_ages(self, model_key: str, exclude_key: str | None = None) -> list[int]:
        """How many days each comparable listing still for sale (seen in the last 14 days) has been up."""
        from datetime import datetime

        rows = self.conn.execute(
            """SELECT key, created_at, flags FROM listings WHERE model_key=? AND COALESCE(created_at, '') != ''
               AND last_seen >= datetime('now', '-14 days')""",
            (model_key,),
        ).fetchall()
        bad = {"broken", "lot", "replica", "part", "wanted", "service"}
        out = []
        for r in rows:
            if r["key"] == exclude_key or bad & set(json.loads(r["flags"] or "[]")):
                continue
            try:
                created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
            except ValueError:
                continue
            now = datetime.now(created.tzinfo) if created.tzinfo else datetime.now()
            out.append(max(0, (now - created).days))
        return out

    def comparable_prices(self, model_key: str, exclude_key: str | None = None, days: int = 365,
                          used_only: bool = False, broken: bool = False) -> list[int]:
        """Asking prices of working, single, real items of this model (used_only: private sellers' used ones,
        not shops and not sealed/new ones)."""
        rows = self.conn.execute(
            f"""SELECT key, price_ron, flags FROM listings
               WHERE model_key=? AND price_ron IS NOT NULL AND price_ron > 0
               AND last_seen >= datetime('now', ?) {"AND COALESCE(business, 0) = 0" if used_only else ""}""",
            (model_key, f"-{days} days"),
        ).fetchall()
        bad = {"lot", "replica", "part", "wanted", "service", "battery"} | ({"new"} if used_only else set())
        out = []
        for r in rows:
            if r["key"] == exclude_key:
                continue
            flags = set(json.loads(r["flags"] or "[]"))
            # broken=True: other broken ones of the model (a parts phone is priced like parts phones)
            if bad & flags or (("broken" in flags) != broken):
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
