"""
Indian Stock Market (NSE / BSE) Trading Calendar & Holiday Validator.

Features:
- Dynamic yearly holiday fetching directly from the official NSE API (https://www.nseindia.com/api/holiday-master?type=trading).
- Local persistent caching (cache/nse_holidays.json) to minimize network overhead and avoid rate limits.
- Built-in multi-year fallback registry (2025, 2026, 2027) in case network requests fail.
- Automatic weekend (Saturday / Sunday) detection.
- Timezone-aware (Asia/Kolkata / IST).
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from pathlib import Path
import pytz
import requests

ROOT = Path(__file__).resolve().parents[1]
CACHE_FILE = ROOT / "cache" / "nse_holidays.json"

# Static multi-year fallback registry in case NSE network fetch fails
STATIC_HOLIDAYS: dict[str, str] = {
    # 2025
    "2025-01-26": "Republic Day",
    "2025-02-26": "Mahashivratri",
    "2025-03-14": "Holi",
    "2025-03-31": "Id-Ul-Fitr",
    "2025-04-10": "Shri Mahavir Jayanti",
    "2025-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2025-04-18": "Good Friday",
    "2025-05-01": "Maharashtra Day",
    "2025-06-07": "Bakri Id",
    "2025-07-06": "Muharram",
    "2025-08-15": "Independence Day",
    "2025-08-27": "Ganesh Chaturthi",
    "2025-10-02": "Mahatma Gandhi Jayanti",
    "2025-10-21": "Dussehra",
    "2025-10-22": "Diwali Balipratipada",
    "2025-11-05": "Prakash Gurpurb Sri Guru Nanak Dev",
    "2025-12-25": "Christmas",
    # 2026
    "2026-01-15": "Municipal Corporation Election - Maharashtra",
    "2026-01-26": "Republic Day",
    "2026-02-15": "Mahashivratri",
    "2026-03-03": "Holi",
    "2026-03-21": "Id-Ul-Fitr (Ramadan Eid)",
    "2026-03-26": "Shri Ram Navami",
    "2026-03-31": "Shri Mahavir Jayanti",
    "2026-04-03": "Good Friday",
    "2026-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2026-05-01": "Maharashtra Day",
    "2026-05-28": "Bakri Id",
    "2026-06-26": "Muharram",
    "2026-08-15": "Independence Day",
    "2026-09-14": "Ganesh Chaturthi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-20": "Dussehra",
    "2026-11-08": "Diwali Laxmi Pujan",
    "2026-11-10": "Diwali-Balipratipada",
    "2026-11-24": "Prakash Gurpurb Sri Guru Nanak Dev",
    "2026-12-25": "Christmas",
    # 2027
    "2027-01-26": "Republic Day",
    "2027-03-08": "Mahashivratri",
    "2027-03-22": "Holi",
    "2027-03-29": "Good Friday",
    "2027-04-14": "Dr. Baba Saheb Ambedkar Jayanti",
    "2027-04-19": "Shri Mahavir Jayanti",
    "2027-05-01": "Maharashtra Day",
    "2027-08-15": "Independence Day",
    "2027-10-02": "Mahatma Gandhi Jayanti",
    "2027-10-11": "Dussehra",
    "2027-10-30": "Diwali Balipratipada",
    "2027-11-14": "Guru Nanak Jayanti",
    "2027-12-25": "Christmas",
}

def fetch_live_nse_holidays() -> dict[str, str] | None:
    """Fetches official trading holidays dynamically from NSE API."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    try:
        session.get("https://www.nseindia.com", timeout=8)
        r = session.get("https://www.nseindia.com/api/holiday-master?type=trading", timeout=8)
        if r.status_code == 200:
            data = r.json()
            cm = data.get("CM", []) or data.get("MF", [])
            holidays: dict[str, str] = {}
            for item in cm:
                dt_str = item.get("tradingDate")
                desc = item.get("description", "Trading Holiday")
                if not dt_str:
                    continue
                try:
                    dt = datetime.strptime(dt_str.strip(), "%d-%b-%Y").date()
                    holidays[dt.isoformat()] = desc
                except Exception:
                    continue
            return holidays
    except Exception:
        pass
    return None

def get_trading_holidays() -> dict[str, str]:
    """
    Returns a unified dictionary of {YYYY-MM-DD: description} of NSE/BSE holidays.
    Loads from cache if fresh, else fetches live from NSE and updates cache.
    Falls back to static multi-year dictionary if network is unavailable.
    """
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    cached_holidays: dict[str, str] = {}

    if CACHE_FILE.exists():
        try:
            cached_holidays = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception:
            cached_holidays = {}

    # If cached holidays are empty or missing, try live fetch
    if not cached_holidays:
        live = fetch_live_nse_holidays()
        if live:
            cached_holidays = live
            try:
                CACHE_FILE.write_text(json.dumps(cached_holidays, indent=2), encoding="utf-8")
            except Exception:
                pass

    # Merge with static fallback to ensure coverage for all years
    merged = {**STATIC_HOLIDAYS, **cached_holidays}
    return merged

def is_trading_day(target_date: date | None = None) -> tuple[bool, str]:
    """
    Checks if a given date (defaulting to current date in Asia/Kolkata timezone)
    is an active NSE/BSE trading day.
    
    Returns:
        (is_trading_day: bool, reason: str)
    """
    if target_date is None:
        ist = pytz.timezone("Asia/Kolkata")
        target_date = datetime.now(ist).date()

    # 1. Weekend Check (Saturday = 5, Sunday = 6)
    weekday = target_date.weekday()
    if weekday == 5:
        return False, f"Weekend (Saturday - {target_date.strftime('%d-%b-%Y')})"
    if weekday == 6:
        return False, f"Weekend (Sunday - {target_date.strftime('%d-%b-%Y')})"

    # 2. Dynamic NSE / BSE Trading Holiday Check
    holidays = get_trading_holidays()
    iso_key = target_date.isoformat()
    if iso_key in holidays:
        reason = holidays[iso_key]
        return False, f"NSE/BSE Holiday ({reason} - {target_date.strftime('%d-%b-%Y')})"

    return True, "Active Trading Day"
