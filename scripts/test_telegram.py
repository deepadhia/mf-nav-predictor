from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import datetime
import pytz
import requests
from dotenv import load_dotenv
from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)
console = Console()

def test_telegram_connection():
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    enabled = os.getenv("TELEGRAM_ENABLED", "true").strip().lower() in ("true", "1", "yes")

    console.print("[bold cyan]==================================================================[/bold cyan]")
    console.print("[bold cyan]  TELEGRAM BOT NOTIFICATION TEST UTILITY                          [/bold cyan]")
    console.print("[bold cyan]==================================================================[/bold cyan]\n")

    if not enabled:
        console.print("[red][X] TELEGRAM_ENABLED is set to false in .env. Enable it to send alerts.[/red]")
        sys.exit(1)

    if not bot_token:
        console.print("[red][X] TELEGRAM_BOT_TOKEN is missing in .env[/red]")
        sys.exit(1)

    if not chat_id:
        console.print("[red][X] TELEGRAM_CHAT_ID is missing in .env[/red]")
        sys.exit(1)

    console.print(f"[dim]Checking Bot Token:[/dim] {bot_token[:8]}...{bot_token[-4:]}")
    console.print(f"[dim]Target Chat ID:[/dim]     {chat_id}\n")

    # 1. Test getMe to verify bot token validity
    console.print("[yellow][1/2] Verifying Telegram bot token validity...[/yellow]")
    try:
        me_resp = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe", timeout=10)
        if me_resp.status_code != 200:
            console.print(f"[red][X] Invalid bot token! Telegram error: {me_resp.text}[/red]")
            sys.exit(1)
        bot_info = me_resp.json().get("result", {})
        console.print(f"[green][OK] Bot Authenticated:[/green] @{bot_info.get('username')} ({bot_info.get('first_name')})")
    except Exception as e:
        console.print(f"[red][X] Network connection to Telegram API failed: {e}[/red]")
        sys.exit(1)

    # 2. Send test message
    console.print("\n[yellow][2/2] Sending test notification to chat...[/yellow]")
    try:
        ist = pytz.timezone("Asia/Kolkata")
        now_str = datetime.now(ist).strftime("%d-%b-%Y | %I:%M:%S %p IST")
    except Exception:
        now_str = datetime.now().strftime("%d-%b-%Y %H:%M:%S")

    message = (
        "🔔 <b>MF NAV PREDICTOR — TEST NOTIFICATION</b>\n"
        f"📅 <i>{now_str}</i>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✅ <b>Telegram Integration is working!</b>\n\n"
        "• <b>Server:</b> Oracle Cloud VM\n"
        "• <b>Check 1 (Pre-Cutoff Pulse):</b> 2:00 PM IST (Mon–Fri)\n"
        "• <b>Check 2 (Decision Cutoff):</b> 2:15 PM IST (Mon–Fri)\n"
        "• <b>Alert Threshold:</b> ≥ 1.0% Dip/Surge\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>You will receive actionable alerts when mutual funds dip ≥ 1.0% before the 2:30 PM cutoff.</i>"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        r = requests.post(url, json=payload, timeout=12)
        if r.status_code == 200:
            console.print("[bold green]==================================================================[/bold green]")
            console.print("[bold green]  [OK] TEST NOTIFICATION SUCCESSFULLY DELIVERED TO YOUR TELEGRAM! [/bold green]")
            console.print("[bold green]==================================================================[/bold green]\n")
        else:
            err = r.json().get("description") if r.headers.get("content-type") == "application/json" else r.text
            console.print(f"[red][X] Telegram API Error ({r.status_code}): {err}[/red]")
            sys.exit(1)
    except Exception as e:
        console.print(f"[red][X] Failed to send Telegram message: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    test_telegram_connection()
