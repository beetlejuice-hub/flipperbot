import json
import time

from flipperbot import tidy
from flipperbot.config import Settings
from flipperbot.db import DB
from flipperbot.models import Listing


def add(db, i, *, days_ago, flags=(), niche="watches", score=5, tier="mid", **extra):
    db.upsert(Listing("olx", str(i), "u", f"listing {i}", price_ron=100))
    sets = {"last_seen": f"datetime('now', '-{days_ago} days')"}
    db.conn.execute(f"UPDATE listings SET last_seen={sets['last_seen']}, flags=?, niche=?, score=?, tier=? WHERE key=?",
                    (json.dumps(list(flags)), niche, score, tier, f"olx:{i}"))
    for k, v in extra.items():
        db.conn.execute(f"UPDATE listings SET {k}=? WHERE key=?", (v, f"olx:{i}"))
    db.conn.commit()


def test_what_the_clean_up_removes_and_keeps(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "photos_dir", property(lambda self: tmp_path / "photos"))
    s = Settings()
    db = DB(":memory:")
    add(db, 1, days_ago=20, flags=["replica"], score=0, tier="bad")  # junk, gone 3 weeks: removed
    add(db, 2, days_ago=3, flags=["replica"], score=0, tier="bad")  # junk, still around: kept for now
    add(db, 3, days_ago=200)  # too old to price anything: removed
    add(db, 4, days_ago=200, starred=1)  # starred: kept
    add(db, 5, days_ago=200, hidden=1)  # hidden (so it never comes back as new): kept
    add(db, 6, days_ago=200, gone_reason="sold", gone_at=time.strftime("%Y-%m-%d"))  # a recent sale: kept
    add(db, 7, days_ago=20, niche="cool", score=2)  # a cool find that didn't make it: removed
    add(db, 8, days_ago=20, score=0, tier="bad", reason="over budget (6000 lei)")  # still prices others: kept
    add(db, 9, days_ago=20, tier="suspect", score=0)  # likely fake: removed
    db.conn.execute("INSERT INTO deals (key, bought_price, bought_at) VALUES ('olx:3', 50, '2026-01-01')")
    db.conn.commit()  # ...but bought: kept after all
    assert tidy.preview(db) == {"junk": 3, "old": 0}
    for name, recent in [("olx_1", False), ("olx_4", False), ("olx_2", True), ("vinted_99", False)]:
        (s.photos_dir / name).mkdir(parents=True)
        (s.photos_dir / name / "1.jpg").write_bytes(b"x" * 1000)
    (s.photos_dir / "olx_2" / "1_q1.jpg").write_bytes(b"x" * 1000)
    out = tidy.run(db, s, log=lambda m: None)
    keys = {r[0] for r in db.conn.execute("SELECT key FROM listings")}
    assert keys == {"olx:2", "olx:3", "olx:4", "olx:5", "olx:6", "olx:8"} and out["listings"] == 3
    assert not (s.photos_dir / "olx_1").exists()  # its listing is gone
    assert (s.photos_dir / "olx_4").exists()  # starred
    assert (s.photos_dir / "olx_2" / "1.jpg").exists()  # recent; its zoomed quarter is fresh too
    assert not (s.photos_dir / "vinted_99").exists()  # hand-added, but its listing is gone
    assert not tidy.due(db)


def test_big_logs_are_cut(tmp_path, monkeypatch):
    monkeypatch.setattr(tidy, "HOME", tmp_path)
    (tmp_path / "bot.log").write_bytes(b"line\n" * 2_000_000)  # 10 MB
    freed = tidy.tidy_logs()
    assert freed > 8_000_000 and (tmp_path / "bot.log").stat().st_size < 1_100_000
