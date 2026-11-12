"""A starter price book shipped with the code, so a fresh install knows market prices
from its first poll instead of after a 25-minute backfill.

Built with `flipperbot export-seed` from a backfill. It keeps only what pricing
needs (title, price, model, flags, link, first photo), no descriptions or
seller details, since the repo is public.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

from .db import DB, now

SEED = Path(__file__).parent / "seed" / "listings.json.gz"
FIELDS = [
    "key", "source", "source_id", "url", "title", "price_ron", "category_id", "brand", "segment",
    "model_key", "refs", "flags", "lot_count", "tier", "est_value_ron", "profit_ron", "reason",
    "first_seen", "last_seen", "photos", "niche", "est_high_ron", "created_at",
]


def export(db: DB, path: Path = SEED) -> int:
    rows = []
    for r in db.conn.execute("SELECT * FROM listings WHERE tier IS NOT NULL"):
        row = {f: r[f] for f in FIELDS}
        row["photos"] = json.dumps(json.loads(r["photos"] or "[]")[:1])
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, separators=(",", ":"))
    return len(rows)


def load_if_empty(db: DB, path: Path = SEED) -> int:
    """Fill an empty database from the seed, or add a newer seed's listings to one that already has
    data (what you already have wins). Seeded listings count as already alerted and summarised, so
    they never send a flood of old finds (`flipperbot show` lists them). Returns how many were added."""
    if not path.exists():
        return 0
    digest = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    empty = not db.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    if not empty and db.kv_get("seed_hash") == digest:
        return 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = json.load(f)
    before = db.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]
    cols = FIELDS + ["notified_tier", "in_digest", "params", "description"]
    q = f"INSERT OR IGNORE INTO listings ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    db.conn.executemany(q, [[r.get(f) for f in FIELDS] + [r.get("tier"), 1, "{}", ""] for r in rows])
    db.conn.commit()
    added = db.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0] - before
    db.kv_set("seed_hash", digest)
    if empty:
        db.kv_set("seeded_at", now())
    if added:
        db.kv_set("rules_version", 0)  # more prices to compare against: judge everything again
    return added
