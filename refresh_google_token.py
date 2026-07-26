"""
refresh_google_token.py — One-time browser OAuth to get a fresh Google token.

Run this ONCE locally whenever the GOOGLE_REFRESH_TOKEN in .env expires or gets revoked:
    python refresh_google_token.py

It will:
  1. Open your browser for Google OAuth (one-time only)
  2. Save the new credentials to token.json
  3. Print the new GOOGLE_REFRESH_TOKEN to paste into .env
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os, json

from dotenv import load_dotenv
load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# ── Try to refresh from .env first ────────────────────────────────────────────
client_id     = os.getenv("GOOGLE_CLIENT_ID")
client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
token_uri     = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")

if client_id and client_secret and refresh_token:
    print("Found existing credentials in .env — trying to refresh...")
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri=token_uri,
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES,
    )
    try:
        creds.refresh(Request())
        print("✅ Existing refresh_token still valid! No need to re-authorize.")
        print(f"\nGOOGLE_REFRESH_TOKEN={creds.refresh_token}")
        sys.exit(0)
    except Exception as exc:
        print(f"❌ Refresh failed: {exc}")
        print("Opening browser OAuth to get a fresh token...\n")

# ── Full OAuth flow ───────────────────────────────────────────────────────────
if not Path("credentials.json").exists():
    print("❌ credentials.json not found.")
    print("   Download it from: console.cloud.google.com → APIs & Services → Credentials")
    print("   → OAuth 2.0 Client IDs → Download JSON → save as credentials.json")
    sys.exit(1)

flow  = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)

# Save to token.json
with open("token.json", "w") as f:
    f.write(creds.to_json())

token_data = json.loads(creds.to_json())
new_refresh = token_data.get("refresh_token", "")

print("\n✅ Browser auth complete! New token saved to token.json")
print("\nCopy these into your .env file:")
print("─" * 60)
print(f"GOOGLE_CLIENT_ID={creds.client_id}")
print(f"GOOGLE_CLIENT_SECRET={creds.client_secret}")
print(f"GOOGLE_REFRESH_TOKEN={new_refresh}")
print(f"GOOGLE_TOKEN_URI={creds.token_uri}")
print("─" * 60)
