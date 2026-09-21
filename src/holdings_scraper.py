from __future__ import annotations

import re
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
import requests
import bs4
import yaml
from rich.console import Console

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIOS_DIR = ROOT / "cache" / "portfolios"
PORTFOLIOS_DIR.mkdir(parents=True, exist_ok=True)
console = Console()

GROWW_TARGETS = {
    "helios": {
        "fund_name": "Helios Flexi Cap Fund Direct Growth",
        "groww_slug": "helios-flexi-cap-fund-direct-growth",
    },
    "motilal_midcap": {
        "fund_name": "Motilal Oswal Midcap Fund Direct Growth",
        "groww_slug": "motilal-oswal-most-focused-midcap-30-fund-direct-growth",
    },
    "trust_smallcap": {
        "fund_name": "TrustMF Small Cap Fund Direct Growth",
        "groww_slug": "trustmf-small-cap-fund-direct-growth",
    },
    "quant_multiasset": {
        "fund_name": "Quant Multi Asset Allocation Fund Growth Option Direct Plan",
        "groww_slug": "quant-multi-asset-allocation-fund-direct-growth",
    },
}

NAME_MAP = {
    "ZOMATO": "ETERNAL",
    "ETERNAL": "ETERNAL",
    "ONE 97 COMMUNICATIONS": "PAYTM",
    "ONE97 COMMUNICATIONS": "PAYTM",
    "PAYTM": "PAYTM",
    "STATE BANK OF INDIA": "SBIN",
    "HDFC BANK": "HDFCBANK",
    "ICICI BANK": "ICICIBANK",
    "AXIS BANK": "AXISBANK",
    "KOTAK MAHINDRA BANK": "KOTAKBANK",
    "INDUSIND BANK": "INDUSINDBK",
    "THE FEDERAL BANK": "FEDERALBNK",
    "FEDERAL BANK": "FEDERALBNK",
    "IDFC FIRST BANK": "IDFCFIRSTB",
    "KARUR VYSYA BANK": "KARURVYSYA",
    "CANARA BANK": "CANBK",
    "RELIANCE INDUSTRIES": "RELIANCE",
    "TATA CONSULTANCY SERVICES": "TCS",
    "INFOSYS": "INFY",
    "HCL TECHNOLOGIES": "HCLTECH",
    "WIPRO": "WIPRO",
    "TECH MAHINDRA": "TECHM",
    "LARSEN & TOUBRO": "LT",
    "LARSEN AND TOUBRO": "LT",
    "BHARTI AIRTEL": "BHARTIARTL",
    "BAJAJ FINANCE": "BAJFINANCE",
    "BAJAJ FINSERV": "BAJAJFINSV",
    "ADANI PORTS": "ADANIPORTS",
    "ADANI ENTERPRISES": "ADANIENT",
    "ADANI GREEN ENERGY": "ADANIGREEN",
    "ADANI POWER": "ADANIPOWER",
    "ADANI TRANSMISSION": "ADANIENSOL",
    "ADANI ENERGY SOLUTIONS": "ADANIENSOL",
    "TATA MOTORS": "TATAMOTORS",
    "MARUTI SUZUKI": "MARUTI",
    "MAHINDRA & MAHINDRA": "M&M",
    "MAHINDRA AND MAHINDRA": "M&M",
    "TITAN COMPANY": "TITAN",
    "TITAN": "TITAN",
    "SUN PHARMACEUTICAL": "SUNPHARMA",
    "NTPC": "NTPC",
    "POWER GRID CORPORATION": "POWERGRID",
    "COAL INDIA": "COALINDIA",
    "TATA STEEL": "TATASTEEL",
    "HINDUSTAN UNILEVER": "HINDUNILVR",
    "ITC": "ITC",
    "NESTLE INDIA": "NESTLEIND",
    "ASIAN PAINTS": "ASIANPAINT",
    "ULTRATECH CEMENT": "ULTRACEMCO",
    "INDUS TOWERS": "INDUSTOWER",
    "DIXON TECHNOLOGIES": "DIXON",
    "PERSISTENT SYSTEMS": "PERSISTENT",
    "COFORGE": "COFORGE",
    "POLYCAB INDIA": "POLYCAB",
    "TRENT": "TRENT",
    "SUPREME INDUSTRIES": "SUPREMEIND",
    "ASTRAL": "ASTRAL",
    "KALYAN JEWELLERS": "KALYANKJIL",
    "VOLTAS": "VOLTAS",
    "APL APOLLO TUBES": "APLAPOLLO",
    "SUNDRAM FASTENERS": "SUNDRMFAST",
    "MAX HEALTHCARE": "MAXHEALTH",
    "BALKRISHNA INDUSTRIES": "BALKRISIND",
    "BHARAT ELECTRONICS": "BEL",
    "CG POWER": "CGPOWER",
    "LUPIN": "LUPIN",
    "AUROBINDO PHARMA": "AUROPHARMA",
    "COROMANDEL INTERNATIONAL": "COROMANDEL",
    "DALMIA BHARAT": "DALBHARAT",
    "PRESTIGE ESTATES": "PRESTIGE",
    "OBEROI REALTY": "OBEROIRLTY",
    "WELSPUN CORP": "WELCORP",
    "ATHER ENERGY": "ATHERENERG",
    "SANSERA ENGINEERING": "SANSERA",
    "SKY GOLD": "SKYGOLD",
    "MULTI COMMODITY EXCHANGE": "MCX",
    "SHADOWFAX TECHNOLOGIES": "SHADOWFAX",
    "LENSKART SOLUTIONS": "LENSKART",
    "NAVIN FLUORINE": "NAVINFLUOR",
    "HDFC LIFE INSURANCE": "HDFCLIFE",
    "NIPPON INDIA ETF GOLD BEES": "GOLDBEES",
    "NIPPON INDIA SILVER ETF": "SILVERBEES",
    "QUANT SILVER ETF": "SILVERBEES",
    "STEEL AUTHORITY OF INDIA": "SAIL",
    "JIO FINANCIAL SERVICES": "JIOFIN",
    "TATA POWER": "TATAPOWER",
    "SAMVARDHANA MOTHERSON": "MOTHERSON",
    "SWAN ENERGY": "SWANCORP",
    "INDIAN RAILWAY CATERING": "IRCTC",
    "NMDC": "NMDC",
    "ORACLE FINANCIAL SERVICES": "OFSS",
    "HEXAWARE TECHNOLOGIES": "HEXAWARE",
    "REDINGTON": "REDINGTON",
    "L&T TECHNOLOGY SERVICES": "LTTS",
    "K.P.R. MILL": "KPRMILL",
    "CERA SANITARYWARE": "CERA",
    "RADICO KHAITAN": "RADICO",
    "JB CHEMICALS": "JBCHEPHARM",
    "ELECON ENGINEERING": "ELECON",
    "SAFARI INDUSTRIES": "SAFARI",
    "PRAJ INDUSTRIES": "PRAJIND",
    "TEJAS NETWORKS": "TEJASNET",
    "KAYNES TECHNOLOGY": "KAYNES",
    "BLS INTERNATIONAL": "BLS",
    "CESC": "CESC",
    "ECLERX SERVICES": "ECLERX",
    "GLOBAL HEALTH": "MEDANTA",
    "ENGINEERS INDIA": "ENGINERSIN",
    "ROUTE MOBILE": "ROUTE",
    "ANAND RATHI WEALTH": "ANANDRATHI",
    "GRAVITA INDIA": "GRAVITA",
    "NEWGEN SOFTWARE": "NEWGEN",
    "GRINDWELL NORTON": "GRINDWELL",
    "APAR INDUSTRIES": "APARINDS",
    "FINOLEX INDUSTRIES": "FINPIPE",
    "TARC": "TARC",
    "KIRLOSKAR OIL ENGINES": "KIRLOSENG",
    "CEAT": "CEATLTD",
    "PRICOL": "PRICOLLTD",
    "HBL POWER SYSTEMS": "HBLPOWER",
    "RATEGAIN TRAVEL": "RATEGAIN",
    "AAVAS FINANCIERS": "AAVAS",
    "ION EXCHANGE": "IONEXCHANG",
    "PREMIER ENERGIES": "PREMIERENE",
    "DLF": "DLF",
    "BLACK BOX": "BBOX",
    "LIFE INSURANCE CORPORATION": "LICI",
    "OIL & NATURAL GAS": "ONGC",
    "OIL AND NATURAL GAS": "ONGC",
    "ZYDUS LIFESCIENCES": "ZYDUSLIFE",
    "BIOCON": "BIOCON",
    "GODREJ PROPERTIES": "GODREJPROP",
    "VARUN BEVERAGES": "VBL",
    "MUTHOOT FINANCE": "MUTHOOTFIN",
}

def resolve_ticker(name: str, search_id: str = "") -> str:
    """Resolves standard NSE trading symbol from company name / Groww search_id."""
    clean = re.sub(r"\b(Ltd|Limited|Corp|Corporation|Inc|India|Co|Holdings)\b", "", name, flags=re.IGNORECASE).strip()
    clean_up = clean.upper()
    for k, v in NAME_MAP.items():
        if k in clean_up:
            return v

    if search_id:
        sid_clean = search_id.replace("-ltd", "").replace("-limited", "").replace("-india", "").replace("-", "").upper()
        for k, v in NAME_MAP.items():
            if k.replace(" ", "") == sid_clean:
                return v

    words = re.findall(r"[A-Za-z0-9]+", clean)
    return words[0].upper() if words else name.upper()

def fetch_groww_holdings(slug: str) -> tuple[list[dict], str, int]:
    """Fetches exact, full market-moving holdings from Groww server-side rendered state."""
    url = f"https://groww.in/mutual-funds/{slug}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()

    soup = bs4.BeautifulSoup(r.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        raise RuntimeError("No __NEXT_DATA__ found on Groww page")

    data = json.loads(script.string)
    mf = data.get("props", {}).get("pageProps", {}).get("mfServerSideData", {})
    raw_holdings = mf.get("holdings", [])
    total_raw_count = len(raw_holdings)

    parsed = []
    portfolio_date = ""
    for h in raw_holdings:
        nature = h.get("nature_name", "")
        inst = str(h.get("instrument_name", ""))

        # Include all active market-moving assets:
        # 1. Direct Equities (excluding derivative futures)
        # 2. Commodity ETFs (Gold BeES, Silver ETF)
        is_market_moving = (
            (nature in ("EQUITY", "COMMODITY") and inst != "Futures")
            or (nature == "MF" and "etf" in str(h.get("company_name", "")).lower())
        )

        if not is_market_moving:
            continue

        raw_weight = h.get("corpus_per")
        if not raw_weight:
            continue
        try:
            w = float(raw_weight)
        except Exception:
            continue

        if w <= 0:
            continue

        name = str(h.get("company_name", "")).strip()
        sid = str(h.get("stock_search_id") or "").strip()
        sym = resolve_ticker(name, sid)

        if not portfolio_date and h.get("portfolio_date"):
            portfolio_date = str(h.get("portfolio_date"))[:10]

        parsed.append({
            "symbol": sym,
            "name": name,
            "weight": round(w, 2),
        })

    # Deduplicate exact symbols if any
    dedup = {}
    for item in parsed:
        s = item["symbol"]
        if s in dedup:
            dedup[s]["weight"] = round(dedup[s]["weight"] + item["weight"], 2)
        else:
            dedup[s] = item

    final_list = list(dedup.values())
    final_list.sort(key=lambda x: x["weight"], reverse=True)
    return final_list, portfolio_date, total_raw_count

def update_fund_portfolio(fund_key: str) -> bool:
    """Updates the portfolio holdings for a specific fund using Groww's official disclosures."""
    target = GROWW_TARGETS.get(fund_key)
    if not target:
        console.print(f"[red]Unknown fund key: {fund_key}[/red]")
        return False

    fund_name = target["fund_name"]
    slug = target["groww_slug"]
    dest_file = PORTFOLIOS_DIR / f"{fund_key}.yaml"

    console.print(f"[cyan]Fetching official Groww portfolio disclosures for [bold]{fund_name}[/bold]...[/cyan]")

    try:
        holdings, p_date, raw_total = fetch_groww_holdings(slug)
        if not holdings:
            console.print(f"[yellow]No valid holdings returned for {slug}[/yellow]")
            return False

        active_weight = round(sum(x["weight"] for x in holdings), 2)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        doc = {
            "fund_name": fund_name,
            "source": "Groww (Official AMC Disclosure)",
            "as_of": p_date or now_str,
            "updated_at": now_str,
            "total_portfolio_items": raw_total,
            "market_moving_holdings_count": len(holdings),
            "total_active_weight": active_weight,
            "holdings": holdings,
        }

        dest_file.write_text(yaml.dump(doc, sort_keys=False), encoding="utf-8")
        console.print(
            f"[green][OK] Refreshed {len(holdings)} market-moving holdings (out of {raw_total} total portfolio items) for {fund_key} "
            f"(Total Active Weight: {active_weight}%, Disclosed As Of: {p_date})[/green]"
        )
        return True

    except Exception as e:
        console.print(f"[red]Error fetching Groww disclosures for {fund_key}: {e}[/red]")
        return False

def main():
    parser = argparse.ArgumentParser(description="Fetch and update mutual fund portfolio holdings from Groww")
    parser.add_argument("--fund", choices=list(GROWW_TARGETS.keys()) + ["all"], default="all", help="Fund to update")
    args = parser.parse_args()

    funds = list(GROWW_TARGETS.keys()) if args.fund == "all" else [args.fund]
    for f in funds:
        update_fund_portfolio(f)

if __name__ == "__main__":
    main()
