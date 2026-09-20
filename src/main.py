from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd
import yaml
import requests
from dotenv import load_dotenv
from rapidfuzz.fuzz import ratio
from rich.console import Console
from rich.table import Table
import yfinance as yf

from upstox_client import search_instrument, ltp
from telegram_notifier import send_nav_alert, is_telegram_configured
from market_calendar import is_trading_day

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=ROOT / ".env", override=True)
CACHE = ROOT / "cache"
CACHE.mkdir(exist_ok=True)
console = Console()

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

def cfg():
    return yaml.safe_load((ROOT / "config" / "funds.yaml").read_text(encoding="utf-8"))

def yahoo_search_fund(name: str) -> str:
    """Searches Yahoo Finance for an Indian mutual fund and returns its ticker."""
    cleaned_q = re.sub(
        r"\b(direct|growth|reg|regular|fund|plan|option|idcw|reinvestment|payout)\b",
        "",
        name,
        flags=re.IGNORECASE,
    ).strip()
    cleaned_q = re.sub(r"\s+", " ", cleaned_q)

    r = requests.get(
        SEARCH_URL,
        params={"q": cleaned_q, "quotesCount": 15, "newsCount": 0},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        timeout=15,
    )
    r.raise_for_status()

    candidates = []
    wanted = re.sub(r"[^a-z0-9 ]", " ", name.lower())

    for q in r.json().get("quotes", []):
        symbol = q.get("symbol")
        qname = q.get("longname") or q.get("shortname") or ""
        qtype = (q.get("quoteType") or "").upper()
        if not symbol or qtype not in {"MUTUALFUND", "FUND"}:
            continue

        score = ratio(wanted, re.sub(r"[^a-z0-9 ]", " ", qname.lower()))
        if "dir" in qname.lower() or "direct" in qname.lower():
            score += 15
        if "gr" in qname.lower() or "growth" in qname.lower():
            score += 10
        if symbol.endswith(".BO"):
            score += 10
        candidates.append((score, symbol, qname))

    if not candidates:
        raise RuntimeError(f"Yahoo fund search found no mutual funds for '{name}' (query: '{cleaned_q}')")

    candidates.sort(reverse=True)
    score, symbol, qname = candidates[0]
    return symbol

def yahoo_holdings(symbol: str) -> list[dict]:
    """Retrieves top holdings for a fund ticker via yfinance."""
    t = yf.Ticker(symbol)
    try:
        th = t.funds_data.top_holdings
    except Exception as e:
        raise RuntimeError(f"Failed to fetch holdings for {symbol}: {e}")

    if th is None or th.empty:
        raise RuntimeError(f"Empty holdings returned for {symbol}")

    rows = []
    for idx, row in th.iterrows():
        s = str(idx).strip().upper()
        name = str(row.get("Name", "")).strip()
        w = row.get("Holding Percent")
        if not s or w is None or pd.isna(w):
            continue
        try:
            w = float(w)
        except Exception:
            continue
        if w <= 1.0:
            w *= 100.0
        rows.append({"symbol": s, "name": name, "weight": round(w, 3)})

    if not rows:
        raise RuntimeError(f"No valid parsed holdings for {symbol}")
    return rows

def upstox_map(yahoo_symbol: str, holding_name: str = "") -> dict | None:
    """Maps a Yahoo holding symbol to an Upstox NSE/BSE equity instrument."""
    clean = yahoo_symbol.upper().replace(".NS", "").replace(".BO", "").strip()

    results = []
    if clean.isdigit() and holding_name:
        first_word = holding_name.split()[0]
        results = search_instrument(first_word)

    if not results:
        results = search_instrument(clean)

    if not results and holding_name:
        first_word = holding_name.split()[0]
        results = search_instrument(first_word)

    eq = [x for x in results if x.get("segment") in ("NSE_EQ", "BSE_EQ")]
    if not eq:
        return None

    exact_nse = [x for x in eq if x.get("segment") == "NSE_EQ" and (x.get("trading_symbol") or "").upper() == clean]
    if exact_nse:
        return exact_nse[0]

    exact_bse = [x for x in eq if (x.get("trading_symbol") or "").upper() == clean]
    if exact_bse:
        return exact_bse[0]

    nse = [x for x in eq if x.get("segment") == "NSE_EQ"]
    return (nse or eq)[0]

def build_mapping(holdings: list[dict]) -> dict:
    """Builds and caches instrument mappings for holding symbols."""
    path = CACHE / "instrument_map.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    changed = False

    for h in holdings:
        s = h["symbol"]
        if s in old:
            continue
        try:
            inst = upstox_map(s, h.get("name", ""))
            if inst:
                old[s] = {
                    "instrument_key": inst["instrument_key"],
                    "trading_symbol": inst.get("trading_symbol"),
                    "isin": inst.get("isin"),
                    "name": inst.get("name"),
                    "segment": inst.get("segment"),
                }
                changed = True
        except Exception as e:
            console.print(f"[yellow]Instrument mapping failed for {s}: {e}[/yellow]")

    if changed or not path.exists():
        path.write_text(json.dumps(old, indent=2), encoding="utf-8")
    return old

def fetch_upstox_prices(mapping: dict) -> dict:
    """Fetches real-time LTP and previous close from Upstox V3 API."""
    keys = list({v["instrument_key"] for v in mapping.values() if v.get("instrument_key")})
    if not keys:
        return {}

    by_token = {}
    chunk_size = 200
    for i in range(0, len(keys), chunk_size):
        chunk = keys[i:i + chunk_size]
        result = ltp(chunk)
        for quote_key, item in result.items():
            token = item.get("instrument_token") or quote_key
            lp = item.get("last_price")
            cp = item.get("cp")
            if lp is not None and cp is not None:
                quote_data = {
                    "ltp": float(lp),
                    "cp": float(cp),
                    "ltt": item.get("ltt"),
                }
                by_token[token] = quote_data
                if quote_key:
                    by_token[quote_key] = quote_data

    return by_token

def yahoo_fallback(symbols: list[str]) -> dict:
    """Fallback price lookup via yfinance for unmapped symbols."""
    out = {}
    for s in symbols:
        y = s if ("." in s or s.isdigit()) else s + ".NS"
        if s.isdigit():
            y = s + ".BO"
        try:
            ticker = yf.Ticker(y)
            hist = ticker.history(period="5d")
            if hist.empty or len(hist) < 2:
                continue
            prev_close = float(hist["Close"].iloc[-2])
            current_price = float(hist["Close"].iloc[-1])
            if prev_close > 0 and current_price > 0:
                out[s] = {"ltp": current_price, "cp": prev_close, "source": "yfinance"}
        except Exception:
            pass
    return out

def main():
    parser = argparse.ArgumentParser(description="Mutual Fund Intraday NAV Predictor")
    parser.add_argument(
        "--force",
        "--ignore-holiday",
        dest="ignore_holiday",
        action="store_true",
        help="Run predictor even on weekends or market holidays",
    )
    parser.add_argument(
        "--force-alert",
        dest="force_alert",
        action="store_true",
        help="Force send Telegram alert regardless of the 1% threshold",
    )
    args = parser.parse_args()

    c = cfg()
    use_fallback = bool(c.get("settings", {}).get("use_yfinance_fallback", True))
    threshold = float(c.get("settings", {}).get("signal_threshold_pct", 0.50))
    min_cov = float(c.get("settings", {}).get("min_coverage_pct", 15.0))
    checkpoint = str(c.get("settings", {}).get("checkpoint_time", "13:30"))

    console.print("[bold cyan]==================================================================[/bold cyan]")
    console.print("[bold cyan]  MUTUAL FUND INTRADAY NAV PREDICTOR (UPSTOX V3 + YFINANCE)      [/bold cyan]")
    console.print("[bold cyan]==================================================================[/bold cyan]\n")

    # 1. Trading Day & Market Holiday Validation
    is_open, reason = is_trading_day()
    if not is_open and not args.ignore_holiday:
        console.print(f"[bold yellow][!] Market Closed Today:[/bold yellow] [yellow]{reason}[/yellow]")
        console.print("[dim]Intraday prediction skipped. (Use '--force' or '--ignore-holiday' to run manually).[/dim]\n")
        return

    summary = []
    fund_results_for_alert = []

    for fund in c["funds"]:
        name = fund["name"]
        configured_symbol = fund.get("symbol")
        console.print(f"[bold white]{name}[/bold white]")

        try:
            yfund = configured_symbol or yahoo_search_fund(name)
            holdings = yahoo_holdings(yfund)
            console.print(f"  [dim]Yahoo Ticker:[/dim] {yfund} | [dim]Holdings Count:[/dim] {len(holdings)}")

            mapping = build_mapping(holdings)
            prices_by_token = fetch_upstox_prices(mapping)

            resolved = []
            missing = []
            for h in holdings:
                m = mapping.get(h["symbol"])
                p = None
                if m:
                    p = prices_by_token.get(m["instrument_key"]) or prices_by_token.get(f"{m.get('segment', 'NSE_EQ')}:{m.get('trading_symbol')}")

                if p and p.get("ltp") is not None and p.get("cp") is not None and p["cp"] > 0:
                    resolved.append({
                        **h,
                        "instrument_key": m["instrument_key"],
                        "trading_symbol": m.get("trading_symbol") or h["symbol"],
                        "ltp": float(p["ltp"]),
                        "cp": float(p["cp"]),
                        "source": "upstox",
                    })
                else:
                    missing.append(h)

            if use_fallback and missing:
                fb = yahoo_fallback([x["symbol"] for x in missing])
                for h in missing[:]:
                    p = fb.get(h["symbol"])
                    if p and p.get("cp", 0) > 0:
                        resolved.append({
                            **h,
                            "trading_symbol": h["symbol"],
                            **p,
                        })
                        missing.remove(h)

            total_weight = sum(x["weight"] for x in resolved)
            raw_contrib = sum((x["weight"] / 100) * (x["ltp"] / x["cp"] - 1) * 100 for x in resolved)
            upstox_weight = sum(x["weight"] for x in resolved if x["source"] == "upstox")
            coverage = total_weight

            normalized_est = (raw_contrib / (total_weight / 100)) if total_weight > 0 else 0.0

            if coverage < min_cov:
                confidence = "LOW"
                signal = "INSUFFICIENT COVERAGE"
            elif normalized_est <= -threshold:
                confidence = "HIGH" if coverage >= 40 and upstox_weight >= 30 else "MEDIUM"
                signal = "DIP (LUMP SUM BUY)"
            elif normalized_est >= threshold:
                confidence = "HIGH" if coverage >= 40 and upstox_weight >= 30 else "MEDIUM"
                signal = "SURGE (AVOID / SKIP)"
            else:
                confidence = "MEDIUM" if coverage >= 40 else "LOW"
                signal = "NORMAL (NO TRIGGER)"

            conf_color = "green" if confidence == "HIGH" else ("yellow" if confidence == "MEDIUM" else "red")
            console.print(
                f"  [bold]Est. NAV Movement (Normalized):[/bold] [bold {'green' if normalized_est >= 0 else 'red'}]{normalized_est:+.2f}%[/bold "
                f"{'green' if normalized_est >= 0 else 'red'}] | "
                f"Raw Contrib: {raw_contrib:+.2f}% | "
                f"Coverage: {coverage:.1f}% (Upstox: {upstox_weight:.1f}%) | "
                f"[{conf_color}]Confidence: {confidence}[/{conf_color}]"
            )

            contrib = []
            for x in resolved:
                ret = (x["ltp"] / x["cp"] - 1) * 100
                contrib.append({
                    "symbol": x.get("trading_symbol", x["symbol"]),
                    "weight": x["weight"],
                    "return": ret,
                    "contribution": (x["weight"] / 100) * ret,
                })
            contrib.sort(key=lambda z: z["contribution"], reverse=True)

            console.print("  [dim]Top Contributors:[/dim]")
            for x in contrib[:3]:
                console.print(
                    f"    [+] {x['symbol']:<14} {x['weight']:>5.2f}% | Return: {x['return']:>+6.2f}% -> Contrib: [green]{x['contribution']:>+6.3f}%[/green]"
                )
            if len(contrib) > 3:
                for x in contrib[-2:]:
                    color = "red" if x['contribution'] < 0 else "green"
                    console.print(
                        f"    [-] {x['symbol']:<14} {x['weight']:>5.2f}% | Return: {x['return']:>+6.2f}% -> Contrib: [{color}]{x['contribution']:>+6.3f}%[/{color}]"
                    )
            console.print()

            summary.append((name, normalized_est, raw_contrib, coverage, upstox_weight, confidence, signal))
            fund_results_for_alert.append({
                "name": name,
                "normalized_est": normalized_est,
                "raw_contrib": raw_contrib,
                "coverage": coverage,
                "upstox_weight": upstox_weight,
                "confidence": confidence,
                "signal": signal,
                "contributors": contrib,
            })

        except Exception as e:
            console.print(f"  [red]ERROR: {e}[/red]\n")
            summary.append((name, None, None, 0, 0, "LOW", "ERROR"))
            fund_results_for_alert.append({
                "name": name,
                "normalized_est": None,
                "raw_contrib": 0,
                "coverage": 0,
                "upstox_weight": 0,
                "confidence": "LOW",
                "signal": "ERROR",
                "contributors": [],
            })

    table = Table(title="MUTUAL FUND ESTIMATED NAV DECISION SUMMARY")
    table.add_column("Fund", style="bold white")
    table.add_column("Est. NAV Change", justify="right")
    table.add_column("Raw Contrib", justify="right")
    table.add_column("Coverage", justify="right")
    table.add_column("Upstox %", justify="right")
    table.add_column("Confidence", justify="center")
    table.add_column("Signal", justify="center")

    for row in summary:
        est_str = "N/A" if row[1] is None else f"{row[1]:+.2f}%"
        color = "green" if (row[1] or 0) > 0 else ("red" if (row[1] or 0) < 0 else "white")
        raw_str = "N/A" if row[2] is None else f"{row[2]:+.2f}%"

        table.add_row(
            row[0],
            f"[{color}]{est_str}[/{color}]",
            raw_str,
            f"{row[3]:.1f}%",
            f"{row[4]:.1f}%",
            row[5],
            row[6],
        )

    console.print(table)
    console.print(
        "\n[dim]Note: 'Est. NAV Change' is normalized across disclosed holdings. "
        "Actual published NAV by AMC includes remaining unpriced holdings, cash drag, expense ratio, and final 3:30 PM closing prices.[/dim]\n"
    )
    # Trigger Telegram Alert if configured
    if is_telegram_configured():
        alert_thresh = float(c.get("settings", {}).get("telegram_alert_threshold_pct", 1.00))
        only_material = bool(c.get("settings", {}).get("telegram_only_on_material_move", True))

        sent, reason = send_nav_alert(
            fund_results_for_alert,
            checkpoint_time=checkpoint,
            threshold=alert_thresh,
            only_on_material=only_material,
            force=args.force_alert,
        )

        if sent:
            console.print(f"[bold green][OK] Telegram lump-sum alert delivered (move >= {alert_thresh:.1f}% detected)![/bold green]\n")
        elif reason == "NO_MATERIAL_MOVE":
            console.print(f"[dim][i] Telegram alert suppressed (no fund moved >= {alert_thresh:.1f}%). Everyday noise avoided.[/dim]\n")
        else:
            console.print(f"[yellow][!] Telegram alert status: {reason}[/yellow]\n")

if __name__ == "__main__":
    main()
