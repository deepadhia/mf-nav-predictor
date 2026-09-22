# Mutual Fund Intraday NAV Predictor & Dip-Buyer Alert

A lightweight, automated personal tool for calculating likely intraday NAV pressure across your mutual funds around **2:30 PM IST** (before the 3:00 PM same-day NAV cut-off) to make informed lump-sum buy decisions.

---

## 🚀 Key Features

* **High Coverage (85%–95%) & HIGH Confidence**: Uses expanded fund portfolio disclosures across 30–70 holdings per fund instead of standard top-10 limits.
* **Auto-Refreshing Disclosures**: Automatically fetches and updates monthly SEBI portfolio releases on-the-fly and via scheduled cron.
* **Ultra-Fast Upstox V3 Batch Pricing**: Queries real-time LTP and previous close for 150+ stocks simultaneously in <100ms.
* **Seamless Fallback**: Automatically falls back to `yfinance` history if an instrument key is unmapped or broker token expires.
* **Actionable Telegram Alerts**: Delivers color-coded daily status digests and Dip-Buying alerts (`🟢 BUY DIP`, `⚪ NORMAL`, `🛑 DO NOT BUY (Surging)`) directly to your Telegram.
* **30-Day Automated Accuracy Tracking**: Logs predictions and reconciles them nightly against official AMC published NAVs with Mean Absolute Error (MAE), RMSE, and Directional Hit Rates.
* **Zero-Cost Oracle Cloud VM Ready**: Fully automated 1-click installer and Linux crontab scheduler.

---

## 🏛️ Architecture & Schedules

* **Check 1 (Early Pulse Check):** 1:30 PM IST (`08:00 UTC` Mon–Fri)
* **Check 2 (Final Decision Check):** 2:30 PM IST (`09:00 UTC` Mon–Fri, 30 min before 3:00 PM SEBI cut-off)
* **Nightly Accuracy Audit:** 11:30 PM IST (`18:00 UTC` Mon–Fri)
* **Disclosures Auto-Refresh:** Every 10 days (1st, 11th, 21st of each month at `06:00 UTC`)

---

## 🛠️ Accuracy & Audit Commands

### 1. View 30-Day Accuracy Report
To inspect overall and per-fund prediction accuracy (MAE in bps, RMSE, Directional Hit %):
```bash
python src/accuracy_report.py
```
*Optional filters:*
```bash
python src/accuracy_report.py --days 14
python src/accuracy_report.py --fund helios
```

### 2. Run Nightly Reconciliation Manually
```bash
python src/reconciler.py
```

---

## 🛠️ Quick Local Setup

### 1. Configure `.env`
Copy `.env.example` to `.env` and fill your credentials:
```bash
cp .env.example .env
```
Fill:
```text
UPSTOX_API_KEY=...
UPSTOX_API_SECRET=...
UPSTOX_ACCESS_TOKEN=...
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

### 2. Install Dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Run Predictor
```bash
python src/main.py
```
*Use `--force` to run outside market hours or on holidays.*
*Use `--refresh-holdings` to scrape the latest online disclosures immediately.*

---

## ☁️ Deploy / Update on Oracle Cloud Instance (OCI)

To deploy or update your Oracle Cloud VM instance:
```bash
cd ~/MFNAVTracker
./scripts/deploy.sh
```

---

## 📊 Tracked Funds & Portfolio Config

Configured in `config/funds.yaml`:
* **Helios Flexi Cap Fund Direct Growth** (`config/portfolios/helios.yaml`)
* **Motilal Oswal Midcap Fund Direct Growth** (`config/portfolios/motilal_midcap.yaml`)
* **TrustMF Small Cap Fund Direct Growth** (`config/portfolios/trust_smallcap.yaml`)
* **Quant Multi Asset Allocation Fund Direct Plan** (`config/portfolios/quant_multiasset.yaml`)

---

## 💡 Lump Sum Strategy Guidelines

* **🟢 DIP DETECTED ($\le -1.0\%$):** Portfolio is under severe downward pressure. Deploy lump sum before 3:00 PM to lock in today's discounted NAV.
* **⚪ NORMAL RANGE ($-1.0\%$ to $+1.0\%$):** Normal market movement. No urgent lump sum trigger.
* **🛑 SURGE / PEAK ($\ge +1.0\%$):** Market is expensive today. Skip lump sum at intraday peaks.
