import os
import requests
from datetime import datetime
import pytz
import re
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)

def is_telegram_configured() -> bool:
    enabled = os.getenv("TELEGRAM_ENABLED", "true").strip().lower() in ("true", "1", "yes")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    return enabled and bool(token) and bool(chat_id)

def clean_fund_name(name: str) -> str:
    """Shortens verbose fund names for a crisp telegram layout."""
    short = re.sub(
        r"\b(Fund|Direct|Plan|Growth|Option|IDCW|Regular)\b",
        "",
        name,
        flags=re.IGNORECASE
    ).strip()
    short = re.sub(r"\s+", " ", short)
    return short

def has_material_move(fund_results: list[dict], threshold: float = 1.0) -> bool:
    """Checks if any fund has an estimated movement exceeding the threshold."""
    for f in fund_results:
        est = f.get("normalized_est")
        if est is not None and abs(est) >= threshold:
            return True
    return False

def build_compact_message(fund_results: list[dict], checkpoint_time: str, threshold: float) -> str:
    """
    Builds a compact, actionable Buy-the-Dip lump-sum decision message:
    - Bigger Dip (<= -1%): BUY DIP TODAY before 2 PM to capture discount.
    - Surge/Rally (>= +1%): AVOID / DO NOT BUY at highs.
    """
    try:
        ist = pytz.timezone("Asia/Kolkata")
        now_ist = datetime.now(ist).strftime("%d-%b-%Y | %I:%M %p IST")
    except Exception:
        now_ist = datetime.now().strftime("%d-%b-%Y")

    header = (
        f"🎯 <b>MF DIP BUYER ALERT ({checkpoint_time} IST)</b>\n"
        f"📅 <i>{now_ist}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    )

    lines = []
    dip_buy_count = 0
    surge_count = 0

    for f in fund_results:
        raw_name = f.get("name", "")
        name = clean_fund_name(raw_name)
        est = f.get("normalized_est")

        if est is None:
            lines.append(f"⚠️ <b>{name}:</b> <i>Data unavailable</i>")
            continue

        est_str = f"{est:+.2f}%"

        # Dip Buying Strategy:
        if est <= -threshold:
            lines.append(f"🟢 <b>{name}:</b> <code>{est_str}</code> ➔ <b>BUY DIP TODAY</b> (before 2 PM)")
            dip_buy_count += 1
        elif est >= threshold:
            lines.append(f"🛑 <b>{name}:</b> <code>{est_str}</code> ➔ <b>DO NOT BUY</b> (Surging / Peak)")
            surge_count += 1
        else:
            lines.append(f"⚪ <b>{name}:</b> <code>{est_str}</code> ➔ <i>No Action</i> (Normal range)")

    body = "\n\n".join(lines)

    # Actionable summary note
    advice_lines = []
    if dip_buy_count > 0:
        advice_lines.append(f"• <b>DIP DETECTED (🟢 &le; -{threshold:.1f}%):</b> Buy before 2:00 PM to lock in today's discounted NAV.")
    if surge_count > 0:
        advice_lines.append(f"• <b>SURGE DETECTED (🛑 &ge; +{threshold:.1f}%):</b> Market expensive today. Skip lump sum at peaks.")
    if not advice_lines:
        advice_lines.append(f"• All funds within normal ±{threshold:.1f}% range. No material dip to deploy lump sum.")

    footer = (
        "\n\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 <b>Lump Sum Strategy:</b>\n" + "\n".join(advice_lines)
    )

    return header + body + footer

def send_nav_alert(
    fund_results: list[dict],
    checkpoint_time: str = "13:30",
    threshold: float = 1.0,
    only_on_material: bool = True,
    force: bool = False
) -> tuple[bool, str]:
    """
    Sends compact Telegram alert based on Dip Buying logic.
    Returns (success: bool, reason: str).
    """
    if not is_telegram_configured():
        return False, "NOT_CONFIGURED"

    if only_on_material and not force and not has_material_move(fund_results, threshold):
        return False, "NO_MATERIAL_MOVE"

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    full_message = build_compact_message(fund_results, checkpoint_time, threshold)

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": full_message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            return True, "DELIVERED"
        else:
            err_desc = r.json().get("description") if r.headers.get("content-type") == "application/json" else r.text
            print(f"[Telegram API Error {r.status_code}]: {err_desc}")
            return False, f"API_ERROR_{r.status_code}"
    except Exception as e:
        print(f"[Telegram Error]: {e}")
        return False, f"EXCEPTION_{e}"
