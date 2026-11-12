"""A starter price book shipped with the code, so a fresh install knows market prices
from its first poll instead of after a 25-minute backfill.

Built with `flipperbot export-seed` from a backfill. It keeps only what pricing
needs (title, price, model, flags, link, first photo), no descriptions or
seller details, since the repo is public.
"""

from __future__ import annotations

import gzip
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
    """Fill an empty database from the seed. Seeded listings count as already alerted and
    summarised, so the first run doesn't send a flood of old finds (`flipperbot show` lists them)."""
    if not path.exists() or db.conn.execute("SELECT COUNT(*) FROM listings").fetchone()[0]:
        return 0
    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = json.load(f)
    cols = FIELDS + ["notified_tier", "in_digest", "params", "description"]
    q = f"INSERT OR IGNORE INTO listings ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    db.conn.executemany(q, [[r.get(f) for f in FIELDS] + [r.get("tier"), 1, "{}", ""] for r in rows])
    db.conn.commit()
    db.kv_set("seeded_at", now())
    return len(rows)
