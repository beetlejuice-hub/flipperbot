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


AUTH = {"likely_genuine": "✅ looks genuine", "unsure": "❓ can't tell if it's genuine", "likely_fake": "⚠️ LIKELY FAKE"}


def deal_text(row: Any, ai: dict[str, Any] | None, note: str | None = None) -> str:
    """The one Telegram message for a real good deal: the deal, then Claude's notes."""
    def e(x: str) -> str:  # Telegram's HTML only needs <, > and & escaped
        return html.escape(x, quote=False)

    lines = [
        f"{EMOJI.get(row['tier'], '')} <b>{LABEL.get(row['tier'], row['tier'])}</b> · {row['price_ron']} lei{' (neg.)' if row['negotiable'] else ''}",
        f"<b>{e(row['title'])}</b>",
        e(row["city"] or ""),
        e(row["reason"] or ""),
    ]
    if row["profit_ron"]:
        lines.append(f"est. resale ~{row['est_value_ron']} lei · profit ~{row['profit_ron']} lei")
    lines.append("")
    if ai and "error" not in ai:
        watches = "; ".join(
            " ".join(x for x in (w.get("brand"), w.get("model"), w.get("reference")) if x)
            for w in ai.get("watches") or []
        )
        lines.append(f"🤖 <b>Claude: {e((ai.get('verdict') or '?').upper())}</b>" + (f" · offer {ai['offer_ron']} lei" if ai.get("offer_ron") else ""))
        if watches:
            lines.append(e(watches))
        lines.append(AUTH.get(ai.get("authenticity"), f"authenticity: {e(str(ai.get('authenticity', '?')))}")
                     + (f": {e(str(ai.get('authenticity_notes'))[:200])}" if ai.get("authenticity_notes") else ""))
        if ai.get("condition"):
            lines.append(f"condition: {e(str(ai['condition'])[:150])}")
        lines.append(f"resale {ai.get('resale_ron_low', '?')}–{ai.get('resale_ron_high', '?')} lei" + (f" · repair ~{ai['repair_cost_ron']} lei" if ai.get("repair_cost_ron") else ""))
        if ai.get("summary"):
            lines.append(e(str(ai["summary"])[:400]))
    elif ai:
        lines.append(f"🤖 Claude couldn't check it: {e(str(ai['error'])[:200])}")
    else:
        lines.append(f"🤖 Not checked by Claude: {e(note or 'unknown reason')}")
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
