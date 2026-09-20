import argparse
import os
import webbrowser
from dotenv import load_dotenv
from upstox_client import oauth_login_url, exchange_code

load_dotenv()

p = argparse.ArgumentParser()
p.add_argument("--redirect-uri", required=True, help="Exactly the redirect URI registered in Upstox Developer Apps")
p.add_argument("--code", help="Authorization code if you already have it")
args = p.parse_args()

if not args.code:
    url = oauth_login_url(args.redirect_uri)
    print("\nOpen this URL in your browser:\n")
    print(url)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print("\nAfter login, Upstox redirects to your redirect URI with ?code=...")
    print("Copy ONLY the code and run this script again with --code.")
else:
    result = exchange_code(args.code, args.redirect_uri)
    token = result.get("access_token")
    if not token:
        print(result)
        raise SystemExit("No access_token returned.")
    print("\nACCESS TOKEN:\n")
    print(token)
    print("\nPut it into .env as:")
    print("UPSTOX_ACCESS_TOKEN=" + token)
