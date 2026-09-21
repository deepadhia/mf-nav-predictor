from __future__ import annotations

import re
import argparse
from datetime import datetime, timezone
from pathlib import Path
import requests
import bs4
import yaml
import yfinance as yf
from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIOS_DIR = ROOT / "cache" / "portfolios"
PORTFOLIOS_DIR.mkdir(parents=True, exist_ok=True)
console = Console()


SCRAPER_TARGETS = {
    "helios": {
        "fund_name": "Helios Flexi Cap Fund Direct Growth",
        "yahoo_symbol": "0P0001RR6I.BO",
        "etmoney_url": "https://www.etmoney.com/mutual-funds/helios-flexi-cap-fund-direct-growth/44147",
    },
    "motilal_midcap": {
        "fund_name": "Motilal Oswal Midcap Fund Direct Growth",
        "yahoo_symbol": "0P00012ALS.BO",
        "etmoney_url": "https://www.etmoney.com/mutual-funds/motilal-oswal-midcap-fund-direct-growth/25852",
    },
    "trust_smallcap": {
        "fund_name": "TrustMF Small Cap Fund Direct Growth",
        "yahoo_symbol": "0P0001TSX8.BO",
        "etmoney_url": "https://www.etmoney.com/mutual-funds/trustmf-small-cap-fund-direct-growth/43110",
    },
    "quant_multiasset": {
        "fund_name": "Quant Multi Asset Allocation Fund Growth Option Direct Plan",
        "yahoo_symbol": "0P0000XW4C.BO",
        "etmoney_url": "https://www.etmoney.com/mutual-funds/quant-multi-asset-allocation-fund-direct-plan-growth/20703",
    },
}

def clean_stock_name_to_symbol(name: str) -> str:
    """Derives standard NSE trading ticker from company name."""
    clean = re.sub(r"\b(Ltd|Limited|Corp|Corporation|Inc|India|Co|Holdings)\b", "", name, flags=re.IGNORECASE).strip()
    clean = re.sub(r"[^a-zA-Z0-9 ]", "", clean)
    words = clean.split()
    if not words:
        return name.upper().replace(" ", "")

    mapping = {
        "HDFC BANK": "HDFCBANK",
        "ICICI BANK": "ICICIBANK",
        "STATE BANK OF": "SBIN",
        "RELIANCE INDUSTRIES": "RELIANCE",
        "INFOSYS": "INFY",
        "TATA CONSULTANCY SERVICES": "TCS",
        "BHARTI AIRTEL": "BHARTIARTL",
        "LARSEN TOUBRO": "LT",
        "BAJAJ FINANCE": "BAJFINANCE",
        "ADANI ENTERPRISES": "ADANIENT",
        "ADANI PORTS": "ADANIPORTS",
        "ADANI GREEN ENERGY": "ADANIGREEN",
        "ONE97 COMMUNICATIONS": "PAYTM",
        "DIXON TECHNOLOGIES": "DIXON",
        "COFORGE": "COFORGE",
        "PERSISTENT SYSTEMS": "PERSISTENT",
        "WELSPUN": "WELCORP",
        "KARUR VYSYA BANK": "KARURVYSYA",
        "ATHER ENERGY": "ATHERENERG",
        "SANSERA ENGINEERING": "SANSERA",
        "SKY GOLD": "SKYGOLD",
        "SHADOWFAX TECHNOLOGIES": "SHADOWFAX",
        "LENSKART SOLUTIONS": "LENSKART",
        "NAVIN FLUORINE": "NAVINFLUOR",
        "HDFC LIFE INSURANCE": "HDFCLIFE",
        "INDUS TOWERS": "INDUSTOWER",
        "NIPPON INDIA ETF GOLD BEES": "GOLDBEES",
    }
    upper_c = " ".join(words).upper()
    for k, v in mapping.items():
        if k in upper_c:
            return v
    return words[0].upper()

def fetch_yahoo_live_holdings(yahoo_symbol: str) -> list[dict]:
    """Fetches real-time top holdings snapshot from Yahoo Finance."""
    try:
        t = yf.Ticker(yahoo_symbol)
        th = t.funds_data.top_holdings
        if th is None or th.empty:
            return []
        rows = []
        for idx, row in th.iterrows():
            s = str(idx).strip().upper().replace(".NS", "").replace(".BO", "")
            name = str(row.get("Name", "")).strip()
            w = row.get("Holding Percent")
            if not s or w is None:
                continue
            try:
                w = float(w)
                if w <= 1.0:
                    w *= 100.0
                rows.append({"symbol": s, "name": name, "weight": round(w, 2)})
            except Exception:
                continue
        return rows
    except Exception:
        return []

def scrape_etmoney_holdings(url: str) -> list[dict]:
    """Scrapes top portfolio holdings table from ET Money."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return []
        soup = bs4.BeautifulSoup(r.text, "html.parser")
        tables = soup.find_all("table")

        holdings = []
        for table in tables:
            headers_text = [th.get_text(strip=True).lower() for th in table.find_all("th")]
            if any("company" in h for h in headers_text) or any("portfolio" in h for h in headers_text):
                rows = table.find_all("tr")
                for row in rows:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 2:
                        name = cols[0]
                        weight_str = cols[1].replace("%", "").strip()
                        try:
                            weight = float(weight_str)
                            symbol = clean_stock_name_to_symbol(name)
                            holdings.append({
                                "symbol": symbol,
                                "name": name,
                                "weight": round(weight, 2),
                            })
                        except ValueError:
                            continue
                if holdings:
                    break
        return holdings
    except Exception:
        return []

def update_fund_portfolio(fund_key: str) -> bool:
    """Dynamically updates portfolio holdings for a specific fund from online feeds."""
    target = SCRAPER_TARGETS.get(fund_key)
    if not target:
        console.print(f"[red]Unknown fund key: {fund_key}[/red]")
        return False

    fund_name = target["fund_name"]
    yahoo_sym = target.get("yahoo_symbol")
    etmoney_url = target.get("etmoney_url")
    dest_file = PORTFOLIOS_DIR / f"{fund_key}.yaml"

    console.print(f"[cyan]Dynamically refreshing holdings for [bold]{fund_name}[/bold]...[/cyan]")

    # 1. Load existing expanded portfolio if present
    existing_holdings = []
    if dest_file.exists():
        try:
            old_data = yaml.safe_load(dest_file.read_text(encoding="utf-8"))
            if isinstance(old_data, dict):
                existing_holdings = old_data.get("holdings", [])
        except Exception:
            existing_holdings = []

    # 2. Fetch latest online top holdings (Yahoo + Web)
    live_yahoo = fetch_yahoo_live_holdings(yahoo_sym) if yahoo_sym else []
    live_web = scrape_etmoney_holdings(etmoney_url) if etmoney_url else []

    # Merge fresh live weights into portfolio
    live_weights = {h["symbol"]: h for h in (live_yahoo + live_web)}

    if not existing_holdings and not live_weights:
        console.print(f"[red]Failed to fetch any online holdings for {fund_key}[/red]")
        return False

    merged_holdings = []
    seen_symbols = set()

    # If we have existing expanded portfolio, update weights and preserve tail holdings
    if existing_holdings:
        for eh in existing_holdings:
            sym = eh["symbol"]
            seen_symbols.add(sym)
            if sym in live_weights:
                merged_holdings.append({
                    "symbol": sym,
                    "name": live_weights[sym].get("name") or eh["name"],
                    "weight": live_weights[sym]["weight"],
                })
            else:
                merged_holdings.append(eh)

    # Add any new stocks discovered in live top holdings
    for sym, item in live_weights.items():
        if sym not in seen_symbols:
            merged_holdings.append(item)
            seen_symbols.add(sym)

    # 3. Clean, deduplicate and normalize
    clean_dict = {}
    for h in merged_holdings:
        sym = str(h.get("symbol", "")).strip().upper()
        if not sym:
            continue
        w = float(h.get("weight", 0))
        if sym in clean_dict:
            clean_dict[sym]["weight"] = max(clean_dict[sym]["weight"], w)
        else:
            clean_dict[sym] = {
                "symbol": sym,
                "name": h.get("name", sym),
                "weight": round(w, 2),
            }

    final_list = list(clean_dict.values())
    raw_total = sum(x["weight"] for x in final_list)

    # If raw sum exceeds 98% (e.g. from overlapping source disclosures), normalize to 95%
    if raw_total > 98.0:
        scale_factor = 95.0 / raw_total
        for x in final_list:
            x["weight"] = round(x["weight"] * scale_factor, 2)

    final_list.sort(key=lambda x: x["weight"], reverse=True)

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    doc = {
        "fund_name": fund_name,
        "as_of": now_str,
        "holdings_count": len(final_list),
        "total_weight": round(sum(x["weight"] for x in final_list), 2),
        "holdings": final_list,
    }

    dest_file.write_text(yaml.dump(doc, sort_keys=False), encoding="utf-8")
    console.print(
        f"[green][OK] Refreshed {len(final_list)} holdings for {fund_key} "
        f"(Total Disclosed Weight: {doc['total_weight']}%, As of: {now_str})[/green]"
    )
    return True


def main():
    parser = argparse.ArgumentParser(description="Dynamically scrape and refresh mutual fund holdings")
    parser.add_argument("--fund", choices=list(SCRAPER_TARGETS.keys()) + ["all"], default="all", help="Fund to update")
    args = parser.parse_args()

    funds = list(SCRAPER_TARGETS.keys()) if args.fund == "all" else [args.fund]
    for f in funds:
        update_fund_portfolio(f)

if __name__ == "__main__":
    main()
