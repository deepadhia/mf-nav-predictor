import os
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

BASE = "https://api.upstox.com"
V3 = "https://api.upstox.com/v3"

def token():
    value = os.getenv("UPSTOX_ACCESS_TOKEN", "").strip()
    if not value:
        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is missing. Put it in .env. "
            "An API key/client_id alone is not enough for market-data calls."
        )
    return value

def headers():
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token()}",
    }

def search_instrument(query, exchanges=None, segments=None):
    params = {
        "query": str(query).strip(),
        "page_number": 1,
        "records": 30,
    }
    if exchanges:
        params["exchanges"] = exchanges
    if segments:
        params["segments"] = segments

    r = requests.get(
        f"{BASE}/v2/instruments/search",
        params=params,
        headers=headers(),
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("data", [])

def ltp(instrument_keys):
    if not instrument_keys:
        return {}
    r = requests.get(
        f"{V3}/market-quote/ltp",
        params={"instrument_key": ",".join(instrument_keys)},
        headers=headers(),
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("data", {})

def full_quote(instrument_keys):
    if not instrument_keys:
        return {}
    r = requests.get(
        f"{V3}/market-quote/quotes",
        params={"instrument_key": ",".join(instrument_keys)},
        headers=headers(),
        timeout=20,
    )
    r.raise_for_status()
    return r.json().get("data", {})

def instrument_search_url():
    return "https://api.upstox.com/v2/instruments/search"

def oauth_login_url(redirect_uri):
    client_id = os.getenv("UPSTOX_API_KEY", "").strip()
    if not client_id:
        raise RuntimeError("UPSTOX_API_KEY is missing in .env")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
    }
    return "https://api.upstox.com/v2/login/authorization/dialog?" + urlencode(params)

def exchange_code(code, redirect_uri):
    client_id = os.getenv("UPSTOX_API_KEY", "").strip()
    client_secret = os.getenv("UPSTOX_API_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RuntimeError("UPSTOX_API_KEY and UPSTOX_API_SECRET are required")
    r = requests.post(
        f"{BASE}/v2/login/authorization/token",
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()
