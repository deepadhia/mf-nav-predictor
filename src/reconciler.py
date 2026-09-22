from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from pathlib import Path
import pytz
import yaml
import yfinance as yf
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[1]
LOGS_DIR = ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PREDICTIONS_CSV = LOGS_DIR / "predictions_history.csv"
ACCURACY_CSV = LOGS_DIR / "accuracy_tracker.csv"

console = Console()
IST = pytz.timezone("Asia/Kolkata")

PREDICTION_HEADERS = [
    "date",
    "timestamp_ist",
    "fund_key",
    "fund_name",
    "estimated_nav_pct",
    "raw_contrib_pct",
    "coverage_pct",
    "upstox_pct",
    "confidence",
    "signal",
]

ACCURACY_HEADERS = [
    "date",
    "fund_key",
    "fund_name",
    "estimated_nav_pct",
    "actual_nav_pct",
    "error_pct",
    "abs_error_bps",
    "directional_match",
    "coverage_pct",
    "confidence",
    "signal",
    "reconciled_at",
]


def load_config() -> dict:
    config_file = ROOT / "config" / "funds.yaml"
    if not config_file.exists():
        return {}
    return yaml.safe_load(config_file.read_text(encoding="utf-8"))


def save_prediction_history(fund_results: list[dict], target_date: date | None = None) -> None:
    """Saves or updates intraday prediction snapshots to predictions_history.csv."""
    now_ist = datetime.now(IST)
    today_str = target_date.isoformat() if target_date else now_ist.strftime("%Y-%m-%d")
    timestamp_str = now_ist.strftime("%Y-%m-%d %H:%M:%S")

    existing_rows: dict[tuple[str, str], dict] = {}
    if PREDICTIONS_CSV.exists():
        with open(PREDICTIONS_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row.get("date", ""), row.get("fund_key", ""))
                if key[0] and key[1]:
                    existing_rows[key] = row

    for r in fund_results:
        f_key = r.get("fund_key") or r.get("key") or ""
        f_name = r.get("name", "")
        est = r.get("normalized_est")
        if est is None:
            continue

        row_key = (today_str, f_key)
        existing_rows[row_key] = {
            "date": today_str,
            "timestamp_ist": timestamp_str,
            "fund_key": f_key,
            "fund_name": f_name,
            "estimated_nav_pct": f"{float(est):.2f}",
            "raw_contrib_pct": f"{float(r.get('raw_contrib', 0.0)):.2f}",
            "coverage_pct": f"{float(r.get('coverage', 0.0)):.1f}",
            "upstox_pct": f"{float(r.get('upstox_weight', 0.0)):.1f}",
            "confidence": str(r.get("confidence", "LOW")),
            "signal": str(r.get("signal", "NORMAL")),
        }

    # Write back sorted by date and fund_key
    sorted_rows = sorted(existing_rows.values(), key=lambda x: (x.get("date", ""), x.get("fund_key", "")))
    with open(PREDICTIONS_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=PREDICTION_HEADERS)
        writer.writeheader()
        for r in sorted_rows:
            filtered_r = {k: r.get(k, "") for k in PREDICTION_HEADERS}
            writer.writerow(filtered_r)


def fetch_historical_nav_series(symbols: dict[str, str], period: str = "2mo") -> dict[str, dict[str, float]]:
    """
    Fetches historical daily closing NAV series for fund symbols.
    Returns: {fund_key: {YYYY-MM-DD: nav_close}}
    """
    out: dict[str, dict[str, float]] = {}
    for fund_key, sym in symbols.items():
        if not sym:
            continue
        try:
            ticker = yf.Ticker(sym)
            hist = ticker.history(period=period)
            if hist.empty:
                continue
            date_to_nav = {}
            for dt, row in hist.iterrows():
                dt_str = dt.strftime("%Y-%m-%d")
                close_val = row.get("Close")
                if close_val is not None and not pd_isna(close_val):
                    date_to_nav[dt_str] = float(close_val)
            out[fund_key] = date_to_nav
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to fetch historical NAV for {fund_key} ({sym}): {e}[/yellow]")
    return out


def pd_isna(val: any) -> bool:
    try:
        import pandas as pd
        return bool(pd.isna(val))
    except Exception:
        return val is None


def reconcile_accuracy(days_back: int = 30) -> list[dict]:
    """
    Reconciles logged intraday predictions against official end-of-day published NAVs.
    Updates accuracy_tracker.csv with actual NAV changes, error margins, and directional hit rates.
    """
    cfg = load_config()
    funds = cfg.get("funds", [])
    symbols = {f.get("key", ""): f.get("symbol", "") for f in funds if f.get("key")}

    if not PREDICTIONS_CSV.exists():
        console.print("[yellow]No predictions history found (predictions_history.csv missing).[/yellow]")
        return []

    # Read predictions
    predictions: list[dict] = []
    with open(PREDICTIONS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            predictions.append(row)

    if not predictions:
        console.print("[yellow]No predictions logged yet.[/yellow]")
        return []

    # Fetch official NAV history
    nav_history = fetch_historical_nav_series(symbols)

    # Read existing accuracy records
    accuracy_records: dict[tuple[str, str], dict] = {}
    if ACCURACY_CSV.exists():
        with open(ACCURACY_CSV, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                key = (row.get("date", ""), row.get("fund_key", ""))
                if key[0] and key[1]:
                    accuracy_records[key] = row

    reconciled_this_run = []
    now_ist_str = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")

    for p in predictions:
        p_date = p.get("date", "")
        f_key = p.get("fund_key", "")
        if not p_date or not f_key:
            continue

        fund_navs = nav_history.get(f_key, {})
        if not fund_navs:
            continue

        # Sort dates in fund_navs
        sorted_dates = sorted(fund_navs.keys())
        if p_date not in sorted_dates:
            continue

        p_idx = sorted_dates.index(p_date)
        if p_idx == 0:
            # Need previous trading day to compute actual NAV change
            continue

        prev_date = sorted_dates[p_idx - 1]
        nav_today = fund_navs[p_date]
        nav_prev = fund_navs[prev_date]

        if nav_prev <= 0:
            continue

        actual_nav_pct = ((nav_today - nav_prev) / nav_prev) * 100.0
        est_nav_pct = float(p.get("estimated_nav_pct", 0.0))
        error_pct = est_nav_pct - actual_nav_pct
        abs_error_bps = abs(error_pct) * 100.0

        # Directional match: both positive, both negative, or both nearly flat (|change| <= 0.05%)
        is_dir_match = (
            (est_nav_pct > 0 and actual_nav_pct > 0)
            or (est_nav_pct < 0 and actual_nav_pct < 0)
            or (abs(est_nav_pct) <= 0.05 and abs(actual_nav_pct) <= 0.05)
        )

        acc_row = {
            "date": p_date,
            "fund_key": f_key,
            "fund_name": p.get("fund_name", ""),
            "estimated_nav_pct": f"{est_nav_pct:+.2f}",
            "actual_nav_pct": f"{actual_nav_pct:+.2f}",
            "error_pct": f"{error_pct:+.2f}",
            "abs_error_bps": f"{abs_error_bps:.1f}",
            "directional_match": "TRUE" if is_dir_match else "FALSE",
            "coverage_pct": p.get("coverage_pct", ""),
            "confidence": p.get("confidence", ""),
            "signal": p.get("signal", ""),
            "reconciled_at": now_ist_str,
        }

        accuracy_records[(p_date, f_key)] = acc_row
        reconciled_this_run.append(acc_row)

    # Save accuracy tracker
    sorted_acc = sorted(accuracy_records.values(), key=lambda x: (x.get("date", ""), x.get("fund_key", "")))
    with open(ACCURACY_CSV, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=ACCURACY_HEADERS)
        writer.writeheader()
        for r in sorted_acc:
            writer.writerow({k: r.get(k, "") for k in ACCURACY_HEADERS})

    return reconciled_this_run


def main():
    parser = argparse.ArgumentParser(description="Nightly Mutual Fund NAV Accuracy Reconciler")
    parser.add_argument("--days", type=int, default=30, help="Days of history to reconcile (default: 30)")
    args = parser.parse_args()

    console.print("[bold cyan]==================================================================[/bold cyan]")
    console.print("[bold cyan]  MUTUAL FUND NAV ACCURACY RECONCILER (NIGHTLY AUDIT)             [/bold cyan]")
    console.print("[bold cyan]==================================================================[/bold cyan]\n")

    reconciled = reconcile_accuracy(days_back=args.days)
    if not reconciled:
        console.print("[yellow]No new predictions pending reconciliation at this time.[/yellow]\n")
        return

    table = Table(title=f"Reconciled Records ({len(reconciled)} items)")
    table.add_column("Date", style="bold white")
    table.add_column("Fund", style="cyan")
    table.add_column("Predicted %", justify="right")
    table.add_column("Actual %", justify="right")
    table.add_column("Diff (bps)", justify="right")
    table.add_column("Direction Match", justify="center")

    for r in reconciled:
        est = float(r["estimated_nav_pct"])
        act = float(r["actual_nav_pct"])
        est_color = "green" if est >= 0 else "red"
        act_color = "green" if act >= 0 else "red"
        match_str = "[bold green]YES[/bold green]" if r["directional_match"] == "TRUE" else "[bold red]NO[/bold red]"

        table.add_row(
            r["date"],
            r["fund_name"],
            f"[{est_color}]{r['estimated_nav_pct']}%[/{est_color}]",
            f"[{act_color}]{r['actual_nav_pct']}%[/{act_color}]",
            f"{r['abs_error_bps']} bps",
            match_str,
        )

    console.print(table)
    console.print(f"\n[bold green][OK] Accuracy database updated -> {ACCURACY_CSV}[/bold green]\n")


if __name__ == "__main__":
    main()
