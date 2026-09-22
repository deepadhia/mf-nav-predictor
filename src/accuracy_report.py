from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime, timedelta
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

ROOT = Path(__file__).resolve().parents[1]
ACCURACY_CSV = ROOT / "logs" / "accuracy_tracker.csv"
console = Console()


def load_accuracy_records() -> list[dict]:
    if not ACCURACY_CSV.exists():
        return []
    records = []
    with open(ACCURACY_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("date") and row.get("fund_key"):
                records.append(row)
    return records


def calculate_metrics(records: list[dict]) -> dict:
    if not records:
        return {}

    total = len(records)
    dir_matches = sum(1 for r in records if r.get("directional_match") == "TRUE")
    dir_acc_pct = (dir_matches / total) * 100.0

    errors_pct = []
    abs_errors_pct = []
    abs_errors_bps = []

    for r in records:
        try:
            err = float(r.get("error_pct", 0.0))
            errors_pct.append(err)
            abs_errors_pct.append(abs(err))
            abs_errors_bps.append(abs(err) * 100.0)
        except Exception:
            continue

    if not abs_errors_pct:
        return {}

    mae_pct = sum(abs_errors_pct) / len(abs_errors_pct)
    mae_bps = sum(abs_errors_bps) / len(abs_errors_bps)
    rmse_pct = math.sqrt(sum(e ** 2 for e in errors_pct) / len(errors_pct))
    max_error_bps = max(abs_errors_bps)

    return {
        "total": total,
        "dir_matches": dir_matches,
        "dir_acc_pct": dir_acc_pct,
        "mae_pct": mae_pct,
        "mae_bps": mae_bps,
        "rmse_pct": rmse_pct,
        "max_error_bps": max_error_bps,
    }


def main():
    parser = argparse.ArgumentParser(description="Mutual Fund NAV Predictor Accuracy & Performance Report")
    parser.add_argument("--days", type=int, default=30, help="Analyze past N days (default: 30)")
    parser.add_argument("--fund", type=str, default="", help="Filter by fund key (e.g., helios, motilal_midcap)")
    parser.add_argument("--limit", type=int, default=15, help="Number of detailed recent logs to display (default: 15)")
    args = parser.parse_args()

    records = load_accuracy_records()
    if not records:
        console.print("[yellow]No accuracy records found. Run the predictor and nightly reconciler first.[/yellow]")
        console.print(f"[dim]Expected accuracy file: {ACCURACY_CSV}[/dim]\n")
        return

    # Filter by days
    cutoff_date = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    filtered = [r for r in records if r.get("date", "") >= cutoff_date]

    # Filter by fund
    if args.fund:
        filtered = [r for r in filtered if r.get("fund_key", "").lower() == args.fund.lower()]

    if not filtered:
        console.print(f"[yellow]No records found matching criteria (days <= {args.days}, fund = '{args.fund}').[/yellow]\n")
        return

    overall_metrics = calculate_metrics(filtered)

    console.print("\n[bold cyan]==================================================================[/bold cyan]")
    console.print(f"[bold cyan]  MUTUAL FUND INTRADAY NAV PREDICTOR - ACCURACY REPORT (PAST {args.days} DAYS)[/bold cyan]")
    console.print("[bold cyan]==================================================================[/bold cyan]\n")

    # KPI Summary Panel
    dir_color = "green" if overall_metrics["dir_acc_pct"] >= 80 else ("yellow" if overall_metrics["dir_acc_pct"] >= 60 else "red")
    mae_color = "green" if overall_metrics["mae_bps"] <= 15 else ("yellow" if overall_metrics["mae_bps"] <= 30 else "red")

    summary_text = (
        f"[bold white]Total Evaluated Fund-Days:[/bold white] {overall_metrics['total']}\n"
        f"[bold white]Directional Hit Rate:[/bold white] [{dir_color}]{overall_metrics['dir_acc_pct']:.1f}%[/{dir_color}] "
        f"({overall_metrics['dir_matches']}/{overall_metrics['total']} correct direction)\n"
        f"[bold white]Mean Absolute Error (MAE):[/bold white] [{mae_color}]{overall_metrics['mae_bps']:.1f} bps[/{mae_color}] "
        f"({overall_metrics['mae_pct']:.2f}%)\n"
        f"[bold white]Root Mean Square Error (RMSE):[/bold white] {overall_metrics['rmse_pct']:.2f}%\n"
        f"[bold white]Max Error Recorded:[/bold white] {overall_metrics['max_error_bps']:.1f} bps"
    )
    console.print(Panel(summary_text, title="[bold green]Executive Performance Metrics[/bold green]", border_style="cyan"))
    console.print()

    # Per-fund Breakdown Table
    by_fund: dict[str, list[dict]] = {}
    for r in filtered:
        k = r.get("fund_key", "unknown")
        by_fund.setdefault(k, []).append(r)

    fund_table = Table(title="PER-FUND ACCURACY BREAKDOWN")
    fund_table.add_column("Fund Name", style="bold white")
    fund_table.add_column("Samples", justify="center")
    fund_table.add_column("Directional Hit %", justify="right")
    fund_table.add_column("Avg Error (bps)", justify="right")
    fund_table.add_column("Avg Error (%)", justify="right")
    fund_table.add_column("Max Error (bps)", justify="right")

    for f_key, f_records in by_fund.items():
        m = calculate_metrics(f_records)
        fname = f_records[0].get("fund_name", f_key)
        d_col = "green" if m["dir_acc_pct"] >= 80 else ("yellow" if m["dir_acc_pct"] >= 60 else "red")
        fund_table.add_row(
            fname,
            str(m["total"]),
            f"[{d_col}]{m['dir_acc_pct']:.1f}%[/{d_col}]",
            f"{m['mae_bps']:.1f} bps",
            f"{m['mae_pct']:.2f}%",
            f"{m['max_error_bps']:.1f} bps",
        )

    console.print(fund_table)
    console.print()

    # Recent Audit Log Table
    sorted_recent = sorted(filtered, key=lambda x: (x.get("date", ""), x.get("fund_key", "")), reverse=True)[:args.limit]
    recent_table = Table(title=f"RECENT EVALUATED DAYS (Last {len(sorted_recent)} entries)")
    recent_table.add_column("Date", style="bold white")
    recent_table.add_column("Fund", style="cyan")
    recent_table.add_column("Predicted %", justify="right")
    recent_table.add_column("Actual %", justify="right")
    recent_table.add_column("Diff (bps)", justify="right")
    recent_table.add_column("Match", justify="center")
    recent_table.add_column("Confidence", justify="center")

    for r in sorted_recent:
        est = float(r["estimated_nav_pct"])
        act = float(r["actual_nav_pct"])
        est_col = "green" if est >= 0 else "red"
        act_col = "green" if act >= 0 else "red"
        match_str = "[bold green]YES[/bold green]" if r.get("directional_match") == "TRUE" else "[bold red]NO[/bold red]"
        recent_table.add_row(
            r.get("date", ""),
            r.get("fund_name", ""),
            f"[{est_col}]{est:+.2f}%[/{est_col}]",
            f"[{act_col}]{act:+.2f}%[/{act_col}]",
            f"{r.get('abs_error_bps', '0')} bps",
            match_str,
            r.get("confidence", "HIGH"),
        )

    console.print(recent_table)
    console.print(f"\n[dim]Audit log location: {ACCURACY_CSV}[/dim]\n")


if __name__ == "__main__":
    main()
