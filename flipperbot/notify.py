"""Telegram alerts. Set up once: message @BotFather on Telegram, /newbot,
put the token in ~/.flipperbot/config.toml, send your bot any message, then
`flipperbot telegram-setup` finds your chat id."""

from __future__ import annotations

import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from . import net
from .config import Settings

EMOJI = {"real_good": "🔥🔥", "good": "🔥", "mid": "🤔", "suspect": "⚠️", "bad": "·"}
LABEL = {"real_good": "REAL GOOD", "good": "GOOD", "mid": "mid", "suspect": "suspect", "bad": "bad"}


def _call(s: Settings, method: str, **params: Any) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{s.telegram_token}/{method}"
    data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
    with net.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
        return json.loads(r.read().decode())


TOKEN = re.compile(r"\d{5,}:[A-Za-z0-9_-]{30,}")


def find_token(text: str) -> str | None:
    """The token out of whatever was pasted: just the token, or BotFather's whole message."""
    m = TOKEN.search(text or "")
    return m.group(0) if m else None


def check_token(s: Settings) -> tuple[dict[str, Any] | None, str]:
    """(bot info, "") if Telegram accepts the token, else (None, why not in plain words)."""
    try:
        return _call(s, "getMe")["result"], ""
    except urllib.error.HTTPError as e:
        if e.code in (401, 404):
            return None, "Telegram says that token is wrong (maybe a character is missing)."
        return None, f"Telegram had a problem: {net.explain(e)}"
    except Exception as e:
        return None, f"Couldn't reach Telegram: {net.explain(e)}"


def enabled(s: Settings) -> bool:
    return bool(s.telegram_token and s.telegram_chat_id)


def send(s: Settings, text: str, photo: str | None = None) -> None:
    if not enabled(s):
        print(text.replace("<b>", "").replace("</b>", ""))
        return
    try:
        if photo and len(text) <= 1024:
            _call(s, "sendPhoto", chat_id=s.telegram_chat_id, photo=photo, caption=text, parse_mode="HTML")
        else:
            # Too long for a photo caption: a message, with the OLX link's preview (its photo) shown.
            _call(s, "sendMessage", chat_id=s.telegram_chat_id, text=text[:4096], parse_mode="HTML",
                  disable_web_page_preview="false" if photo else "true")
    except Exception as e:  # never let a failed alert stop the bot
        print(f"telegram failed: {e}\n{text}")




def estimate(row: Any, ai: dict[str, Any] | None) -> tuple[int | None, int | None, int | None, str]:
    """The one realistic estimate shown everywhere: (low, high, profit, source). Claude's range when it
    has checked (it looked at this exact watch and sold prices), else the bot's realistic range from
    similar listings. Profit counts from the low end, minus repair."""
    if ai and "error" not in ai and ai.get("resale_ron_high"):
        hi = int(ai["resale_ron_high"])
        lo = int(ai.get("resale_ron_low") or hi)
        return lo, hi, lo - (row["price_ron"] or 0) - int(ai.get("repair_cost_ron") or 0), "Claude"
    lo = row["est_value_ron"]
    hi = row["est_high_ron"] if "est_high_ron" in row.keys() else None
    return lo, hi or lo, row["profit_ron"], "similar listings"


def money(lo: int | None, hi: int | None) -> str:
    if not lo:
        return "?"
    return f"{lo:,}–{hi:,} lei".replace(",", ".") if hi and hi != lo else f"~{lo:,} lei".replace(",", ".")


def deal_text(row: Any, ai: dict[str, Any] | None, note: str | None = None) -> str:
    """The Telegram message for a confirmed deal, short: price → realistic value, Claude's call, one line, link."""
    def e(x: str) -> str:  # Telegram's HTML only needs <, > and & escaped
        return html.escape(x, quote=False)

    lo, hi, profit, src = estimate(row, ai)
    lot = " · LOT" if "lot" in (row["flags"] or "") else ""
    from . import niches

    icon = niches.get(row["niche"] if "niche" in row.keys() else None).icon
    head = f"{icon} {EMOJI.get(row['tier'], '')} <b>{row['price_ron']:,} lei</b>".replace(",", ".")
    if lo:
        head += f" → sells for {money(lo, hi)}"
    if profit and profit > 0:
        head += f" (+{profit:,})".replace(",", ".")
    try:
        liq = json.loads(row["liquidity"]) if "liquidity" in row.keys() and row["liquidity"] else None
    except (TypeError, ValueError):
        liq = None
    if liq:
        head += f" · ⏱ sells {liq['label']}"
    lines = [head + lot, f"<b>{e(row['title'][:80])}</b>"]
    if ai and "error" not in ai:
        verdict = (ai.get("verdict") or "?").upper()
        sure = f" · {ai['confidence']}% sure" if isinstance(ai.get("confidence"), (int, float)) else ""
        offer = f" · offer {ai['offer_ron']:,}".replace(",", ".") if ai.get("offer_ron") else ""
        auth = {"likely_genuine": "", "unsure": " · ❓ authenticity unsure", "likely_fake": " · ⚠️ LIKELY FAKE"}.get(ai.get("authenticity"), "")
        lines.append(f"🤖 {verdict}{sure}{offer}{auth}")
        if "lot" in (row["flags"] or ""):
            best = sorted((w for w in (ai.get("items") or ai.get("watches") or []) if w.get("notable")),
                          key=lambda w: -(w.get("value_ron") or 0))[:3]
            if best:
                lines.append("⭐ " + e(", ".join(" ".join(x for x in (w.get("brand"), w.get("model")) if x) for w in best)))
        if ai.get("summary"):
            lines.append(e(str(ai["summary"])[:160]))
    elif note:
        lines.append(f"🤖 not checked: {e(note)}")
    lines.append(row["url"])
    return "\n".join(lines)


def digest_text(rows: list[Any]) -> str:
    e = html.escape
    out = [f"<b>Daily second look: {len(rows)} listings</b>"]
    for r in rows[:40]:
        out.append(f"{EMOJI.get(r['tier'], '')} {r['price_ron']} lei · <a href=\"{e(r['url'])}\">{e(r['title'][:60])}</a> · {e((r['reason'] or '')[:80])}")
    if len(rows) > 40:
        out.append(f"…and {len(rows) - 40} more: run `flipperbot show --tier mid`")
    return "\n".join(out)
