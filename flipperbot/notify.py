"""Telegram alerts. Set up once: message @BotFather on Telegram, /newbot,
put the token in ~/.flipperbot/config.toml, send your bot any message, then
`flipperbot telegram-setup` finds your chat id."""

from __future__ import annotations

import html
import json
import urllib.parse
import urllib.request
from typing import Any

from .config import Settings

EMOJI = {"real_good": "🔥🔥", "good": "🔥", "mid": "🤔", "suspect": "⚠️", "bad": "·"}
LABEL = {"real_good": "REAL GOOD", "good": "GOOD", "mid": "mid", "suspect": "suspect", "bad": "bad"}


def _call(s: Settings, method: str, **params: Any) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{s.telegram_token}/{method}"
    data = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}).encode()
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=30) as r:
        return json.loads(r.read().decode())


def enabled(s: Settings) -> bool:
    return bool(s.telegram_token and s.telegram_chat_id)


def send(s: Settings, text: str, photo: str | None = None) -> None:
    if not enabled(s):
        print(text.replace("<b>", "").replace("</b>", ""))
        return
    try:
        if photo:
            _call(s, "sendPhoto", chat_id=s.telegram_chat_id, photo=photo, caption=text[:1024], parse_mode="HTML")
        else:
            _call(s, "sendMessage", chat_id=s.telegram_chat_id, text=text[:4096], parse_mode="HTML", disable_web_page_preview="true")
    except Exception as e:  # never let a failed alert stop the bot
        print(f"telegram failed: {e}\n{text}")


def listing_text(row: Any, change: str = "new") -> str:
    e = html.escape
    tier = row["tier"]
    head = f"{EMOJI.get(tier, '')} <b>{LABEL.get(tier, tier)}</b>"
    if change == "price_drop":
        head += " · price dropped"
    lines = [
        head,
        f"<b>{e(row['title'])}</b>",
        f"{row['price_ron']} lei{' (neg.)' if row['negotiable'] else ''} · {e(row['city'] or '')}",
        e(row["reason"] or ""),
    ]
    if row["profit_ron"]:
        lines.append(f"est. resale ~{row['est_value_ron']} lei · profit ~{row['profit_ron']} lei")
    lines.append(row["url"])
    return "\n".join(lines)


def ai_text(row: Any, ai: dict[str, Any]) -> str:
    e = html.escape
    if "error" in ai:
        return f"🤖 Claude couldn't check <b>{e(row['title'])}</b>: {e(str(ai['error'])[:300])}"
    watches = "; ".join(
        " ".join(x for x in (w.get("brand"), w.get("model"), w.get("reference")) if x) + f" ({w.get('confidence', '?')})"
        for w in ai.get("watches") or []
    )
    verdict = (ai.get("verdict") or "?").upper()
    lines = [
        f"🤖 <b>{verdict}</b> · {e(row['title'])}",
        f"{e(watches)}",
        f"authenticity: {e(str(ai.get('authenticity', '?')))}",
        f"resale {ai.get('resale_ron_low', '?')}–{ai.get('resale_ron_high', '?')} lei · repair ~{ai.get('repair_cost_ron', 0)} lei · asking {row['price_ron']}",
    ]
    if ai.get("offer_ron"):
        lines.append(f"offer: {ai['offer_ron']} lei")
    if ai.get("summary"):
        lines.append(e(ai["summary"]))
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
