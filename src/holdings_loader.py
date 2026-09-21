from __future__ import annotations

import time
import json
from pathlib import Path
from datetime import datetime, timezone
import yaml
from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIOS_DIR = ROOT / "cache" / "portfolios"
FALLBACK_DIR = ROOT / "config" / "portfolios"
PORTFOLIOS_DIR.mkdir(parents=True, exist_ok=True)
console = Console()


# Number of days after which local portfolio disclosure is considered stale
MAX_PORTFOLIO_AGE_DAYS = 10

def is_portfolio_stale(file_path: Path, max_age_days: int = MAX_PORTFOLIO_AGE_DAYS) -> bool:
    """Returns True if the portfolio file does not exist or is older than max_age_days."""
    if not file_path.exists():
        return True
    try:
        mtime = file_path.stat().st_mtime
        age_days = (time.time() - mtime) / 86400
        return age_days > max_age_days
    except Exception:
        return False

def load_portfolio_holdings(fund_key: str, auto_refresh: bool = True) -> list[dict] | None:
    """
    Loads expanded portfolio holdings from local YAML or JSON.
    If the file is missing or older than MAX_PORTFOLIO_AGE_DAYS, it automatically
    triggers an online refresh to keep holdings up to date.
    Returns a list of dicts: [{'symbol': str, 'name': str, 'weight': float}, ...]
    or None if unavailable.
    """
    yaml_file = PORTFOLIOS_DIR / f"{fund_key}.yaml"
    json_file = PORTFOLIOS_DIR / f"{fund_key}.json"

    target_file = None
    for p in [yaml_file, json_file, FALLBACK_DIR / f"{fund_key}.yaml", FALLBACK_DIR / f"{fund_key}.json"]:
        if p.exists():
            target_file = p
            break

    if target_file is None:
        target_file = yaml_file

    # Auto-refresh if stale or missing
    if auto_refresh and is_portfolio_stale(target_file):
        try:
            from holdings_scraper import update_fund_portfolio
            console.print(f"[yellow]Holdings for '{fund_key}' are older than {MAX_PORTFOLIO_AGE_DAYS} days. Auto-refreshing from online sources...[/yellow]")
            update_fund_portfolio(fund_key)
        except Exception as e:
            console.print(f"[dim]Auto-refresh failed for {fund_key} ({e}), continuing with cached data.[/dim]")

    # Reload target file after refresh
    for p in [yaml_file, json_file, FALLBACK_DIR / f"{fund_key}.yaml", FALLBACK_DIR / f"{fund_key}.json"]:
        if p.exists():
            target_file = p
            break

    if not target_file or not target_file.exists():
        return None


    data = None
    try:
        if target_file.suffix == ".yaml":
            data = yaml.safe_load(target_file.read_text(encoding="utf-8"))
        else:
            data = json.loads(target_file.read_text(encoding="utf-8"))
    except Exception:
        data = None

    if not data or not isinstance(data, dict):
        return None

    raw_holdings = data.get("holdings", [])
    if not raw_holdings:
        return None

    parsed = []
    for h in raw_holdings:
        s = str(h.get("symbol", "")).strip().upper()
        name = str(h.get("name", "")).strip()
        w = h.get("weight")
        if not s or w is None:
            continue
        try:
            w = float(w)
        except Exception:
            continue
        parsed.append({
            "symbol": s,
            "name": name,
            "weight": round(w, 3),
        })

    return parsed if parsed else None

def get_portfolio_meta(fund_key: str) -> dict:
    """Returns metadata for the fund portfolio if present."""
    yaml_file = PORTFOLIOS_DIR / f"{fund_key}.yaml"
    if yaml_file.exists():
        try:
            data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                mtime = yaml_file.stat().st_mtime
                age_days = int((time.time() - mtime) / 86400)
                return {
                    "as_of": data.get("as_of", "Latest"),
                    "fund_name": data.get("fund_name", ""),
                    "age_days": age_days,
                }
        except Exception:
            pass
    return {}
