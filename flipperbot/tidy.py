"""Keep the bot light: a daily clean-up of what no longer helps.

What grows without end: listings nobody will look at again, photos saved for Claude's checks (up to 8 photos and 16
zoomed quarters per check), and the log files. Kept, always: what you starred, hid, bought or sold, what Claude
checked in the last year, listings that sold lately (the price book's best evidence), and anything seen lately.

Removed:
- junk not seen for 2 weeks: replicas, accessories and parts, shop listings, women's and fast fashion, wanted ads,
  cool finds and lots that didn't make the cut;
- any other listing not seen for 6 months (too old to price anything: comparisons use the last months);
- Claude's zoomed photo quarters after 3 days; a listing's photos 3 weeks after it was last seen (or when it's gone
  from the database); photos you added by hand stay while their listing does;
- log files over 5 MB are cut to their last 1 MB.
Then, if much was removed, the database file is compacted (VACUUM).
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any, Callable

from .config import HOME, Settings
from .db import DB

JUNK_FLAGS = ("replica", "part", "dealer", "not_mens", "fast_fashion", "wanted", "service")
KEEP = """starred = 0 AND hidden = 0 AND key NOT IN (SELECT key FROM deals)
          AND (ai IS NULL OR ai_at < datetime('now', '-365 days'))
          AND NOT (COALESCE(gone_reason, '') = 'sold' AND COALESCE(gone_at, '') >= datetime('now', '-180 days'))"""


def due(db: DB) -> bool:
    return time.time() - db.kv_get("tidied_at", 0) >= 86400


def _junk_where() -> str:
    flags = " OR ".join(f"flags LIKE '%\"{f}\"%'" for f in JUNK_FLAGS)
    return f"""last_seen < datetime('now', '-14 days') AND {KEEP} AND (
               ({flags}) OR (COALESCE(niche, '') = 'cool' AND COALESCE(score, 0) < 4)
               OR (COALESCE(niche, '') = 'lots' AND COALESCE(score, 0) < 3) OR tier = 'suspect')"""


def _old_where() -> str:
    return f"last_seen < datetime('now', '-180 days') AND {KEEP}"


def preview(db: DB) -> dict[str, int]:
    """How many listings a clean-up would remove now, without removing anything."""
    c = db.conn
    return {"junk": c.execute(f"SELECT COUNT(*) FROM listings WHERE {_junk_where()}").fetchone()[0],
            "old": c.execute(f"SELECT COUNT(*) FROM listings WHERE {_old_where()} AND NOT ({_junk_where()})").fetchone()[0]}


def _folder_size(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def tidy_photos(db: DB, s: Settings) -> tuple[int, int]:
    """Remove photos nobody needs any more. Returns (folders removed, bytes freed)."""
    root = s.photos_dir
    if not root.exists():
        return 0, 0
    keep_days = {r["key"].replace(":", "_"): r for r in db.conn.execute(
        """SELECT key, last_seen, starred, source, (key IN (SELECT key FROM deals)) AS dealt,
                  last_seen >= datetime('now', '-21 days') AS recent FROM listings""")}
    removed, freed, now = 0, 0, time.time()
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        r = keep_days.get(folder.name)
        hand = folder.name.startswith(("vinted_", "manual_"))  # the only copy of what you added by hand
        if r is None or not (r["recent"] or r["starred"] or r["dealt"] or (hand and r is not None)):
            freed += _folder_size(folder)
            shutil.rmtree(folder, ignore_errors=True)
            removed += 1
            continue
        for tile in folder.glob("*_q[1-4].jpg"):  # the zoomed quarters: only used during a check
            if now - tile.stat().st_mtime > 3 * 86400:
                freed += tile.stat().st_size
                tile.unlink(missing_ok=True)
    return removed, freed


def tidy_logs(limit: int = 5_000_000, keep: int = 1_000_000) -> int:
    """Cut big log files to their last `keep` bytes. Returns bytes freed."""
    freed = 0
    for name in ("bot.log", "app.log", "claude.log", "run.log"):
        p = HOME / name
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > limit:
            with open(p, "rb") as f:
                f.seek(size - keep)
                tail = f.read()
            tail = tail[tail.find(b"\n") + 1:]  # start at a whole line
            p.write_bytes(b"[older lines removed by the daily clean-up]\n" + tail)
            freed += size - p.stat().st_size
    return freed


def run(db: DB, s: Settings, log: Callable[[str], None] = print, vacuum: bool | None = None) -> dict[str, Any]:
    """The daily clean-up. Returns what it did."""
    c = db.conn
    gone_keys = [r[0] for r in c.execute(f"SELECT key FROM listings WHERE ({_junk_where()}) OR ({_old_where()})")]
    for i in range(0, len(gone_keys), 500):
        part = gone_keys[i:i + 500]
        marks = ",".join("?" * len(part))
        c.execute(f"DELETE FROM listings WHERE key IN ({marks})", part)
        c.execute(f"DELETE FROM prices WHERE key IN ({marks})", part)
    c.commit()
    folders, photo_bytes = tidy_photos(db, s)
    log_bytes = tidy_logs()
    db.kv_set("tidied_at", time.time())
    if vacuum is None:
        vacuum = len(gone_keys) >= 1000 or time.time() - db.kv_get("vacuumed_at", 0) > 7 * 86400
    if vacuum and db.path != ":memory:":
        c.execute("VACUUM")
        db.kv_set("vacuumed_at", time.time())
    out = {"listings": len(gone_keys), "photo_folders": folders, "mb_freed": round((photo_bytes + log_bytes) / 1e6, 1),
           "listings_left": c.execute("SELECT COUNT(*) FROM listings").fetchone()[0]}
    if out["listings"] or out["photo_folders"] or out["mb_freed"]:
        log(f"  clean-up: removed {out['listings']} old or junk listings ({out['listings_left']} left), "
            f"{out['photo_folders']} photo folders, {out['mb_freed']} MB freed")
    return out
