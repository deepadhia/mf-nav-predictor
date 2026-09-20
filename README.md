# MF NAV Timing — Upstox primary + yfinance fallback

Purpose: a lightweight personal tool for checking the likely intraday NAV pressure of four mutual funds around 1 PM before deploying a lump sum.

## Architecture

Latest available fund holdings
→ Yahoo fund_holding_info
→ Upstox NSE instrument mapping
→ Upstox V3 LTP + previous close
→ yfinance fallback only when Upstox cannot price a holding
→ weighted portfolio movement
→ 1 PM decision view

Upstox V3's LTP response includes LTP and previous close (`cp`), which is exactly what this calculation needs.

## 1. Create `.env`

Copy:

```text
.env.example
```

to:

```text
.env
```

Fill:

```text
UPSTOX_API_KEY=...
UPSTOX_API_SECRET=...
UPSTOX_ACCESS_TOKEN=...
```

Do NOT commit `.env`.

### API key vs access token

Your Upstox API key/client ID is not itself the bearer token used for market-data requests.

Upstox uses OAuth 2.0. You need an access token. See the official authentication documentation.

If you already have a valid access token, just paste it into `.env`.

If not, register your exact redirect URI in the Upstox Developer App and run:

```bash
python src/upstox_login.py --redirect-uri "YOUR_REGISTERED_REDIRECT_URI"
```

Log in, copy the `code` from the redirect URL, then:

```bash
python src/upstox_login.py --redirect-uri "YOUR_REGISTERED_REDIRECT_URI" --code "THE_CODE"
```

Put the returned token in `.env`.

## 2. Install

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

## 3. Run

```bash
python src/main.py
```

That's it.

## What it does

For each of:

- Helios Flexi Cap Fund Direct Growth
- Motilal Oswal Midcap Fund Direct Growth
- TrustMF Small Cap Fund Direct Growth
- Quant Multi Asset Allocation Fund Direct Plan Growth

it:

1. Searches Yahoo for the fund.
2. Gets Yahoo's latest available holdings.
3. Maps each stock to Upstox's NSE equity instrument.
4. Gets Upstox LTP and previous close.
5. Calculates:

   `holding_weight × (LTP / previous_close - 1)`

6. Adds the contributions.
7. Reports coverage and how much of the estimate came from Upstox.
8. Falls back to yfinance for unpriced symbols if enabled.

## Why Upstox primary?

Upstox V3 market quotes are exchange-derived and provide current LTP plus previous close. The API supports batch quotes, so the script can fetch many holdings efficiently.

## Why yfinance fallback?

Some Yahoo fund holdings can have symbol mismatches or instruments unavailable through the Upstox search. Instead of throwing away the whole estimate, the script can price those holdings with yfinance.

The output explicitly separates:

- `Coverage`: percentage of fund weight successfully priced
- `Upstox`: percentage of fund weight priced through Upstox

## Interpretation

Example:

```text
TrustMF Small Cap
Est. NAV pressure: -1.21%
Coverage: 91.4%
Upstox: 88.7%
Confidence: HIGH
```

This means the currently disclosed portfolio has approximately 1.21% downward price pressure relative to previous closes.

It does NOT mean the final NAV will be exactly -1.21%.

There are still:
- stocks moving between 1 PM and close
- stale/incomplete fund holdings
- cash/debt/other assets
- portfolio changes after the disclosure date
- different valuation conventions for some assets

## Don't overcomplicate it

This is intentionally a small personal research script.

Do not add:
- ML
- a database
- a dashboard
- automated orders
- broker execution

until the signal has demonstrated useful historical accuracy.

For the first 20–30 market sessions, record:

```text
1 PM estimate
actual published NAV change
absolute error
direction correct?
```

Then decide whether it deserves further work.

## Official Upstox docs

Authentication:
https://upstox.com/developer/api-documentation/authentication/

LTP V3:
https://upstox.com/developer/api-documentation/ltp-v3/

Full Market Quote V3:
https://upstox.com/developer/api-documentation/get-full-market-quote-v3/

Instrument Search:
https://upstox.com/developer/api-documentation/instrument-search/
