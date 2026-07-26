"""
Google Calendar + Meet scheduling. Stage 2 — post-test only: interviews
should be scheduled off the FINAL (post-test) rank, not the pre-test
shortlist.

Auth priority:
  1. GOOGLE_* env vars in .env  (works both locally and on cloud)
  2. token.json file             (local dev fallback)
  3. credentials.json + browser OAuth  (first-time local setup only)
"""

import datetime
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

# Module-level cache — authenticate once per process, reuse for every candidate.
_CACHED_CREDS: Credentials | None = None


def _creds_from_env() -> Credentials | None:
    """Build Credentials from .env / environment variables and immediately refresh."""
    client_id     = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    token_uri     = os.getenv("GOOGLE_TOKEN_URI", "https://oauth2.googleapis.com/token")

    if not (client_id and client_secret and refresh_token):
        print("  [auth] GOOGLE_* env vars missing — skipping env auth.")
        return None

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
        print("  [auth] ✅ Authenticated via .env GOOGLE_REFRESH_TOKEN")
        return creds
    except Exception as exc:  # noqa: BLE001
        print(f"  [auth] ❌ Env token refresh failed: {exc}")
        print("  [auth] The GOOGLE_REFRESH_TOKEN in .env may be expired or revoked.")
        print("  [auth] Run once with browser OAuth to get a fresh token:")
        print("         python refresh_google_token.py")
        return None


def _creds_from_streamlit_secrets() -> Credentials | None:
    """Try st.secrets — safe import so this module works without Streamlit installed."""
    try:
        import streamlit as st  # noqa: PLC0415
        if "google_token" in st.secrets:
            print("  [auth] ✅ Authenticated via Streamlit secrets.")
            return Credentials.from_authorized_user_info(dict(st.secrets["google_token"]), SCOPES)
    except Exception:  # noqa: BLE001
        pass
    return None


def authenticate_google() -> Credentials:
    """Return valid Google Calendar credentials (cached after first call)."""
    global _CACHED_CREDS

    if _CACHED_CREDS and _CACHED_CREDS.valid:
        return _CACHED_CREDS

    # Build fresh credentials
    creds = (
        _creds_from_streamlit_secrets()
        or _creds_from_env()
        or (
            Credentials.from_authorized_user_file("token.json", SCOPES)
            if os.path.exists("token.json")
            else None
        )
    )

    # Refresh if we have a refresh_token but no valid access token
    if creds and not creds.valid:
        if creds.refresh_token:
            try:
                creds.refresh(Request())
                print("  [auth] ✅ Token refreshed from token.json")
            except Exception as exc:  # noqa: BLE001
                print(f"  [auth] ❌ token.json refresh failed: {exc}")
                creds = None
        else:
            creds = None

    if not creds:
        print("  [auth] ⚠️  All stored credentials failed — opening browser OAuth (one-time).")
        print("  [auth] After this, run  python refresh_google_token.py  to save to .env.")
        if not os.path.exists("credentials.json"):
            raise FileNotFoundError(
                "Google credentials not found. "
                "Set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET / GOOGLE_REFRESH_TOKEN in .env, "
                "or place credentials.json next to the app."
            )
        flow  = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
        print("  [auth] ✅ New token saved to token.json")

    _CACHED_CREDS = creds
    return creds



def create_interview_event(
    candidate_email: str,
    candidate_name: str,
    start_time: datetime.datetime,
    duration_minutes: int = 30,
) -> str:
    """Creates a Google Calendar event with a Google Meet link. Returns the Meet URL."""
    creds   = authenticate_google()
    service = build("calendar", "v3", credentials=creds)

    end_time = start_time + datetime.timedelta(minutes=duration_minutes)

    event = {
        "summary": f"Interview: {candidate_name} & myNachiketa",
        "description": "Automated interview scheduled via AI Screening Platform.",
        "start": {"dateTime": start_time.isoformat(), "timeZone": "UTC"},
        "end":   {"dateTime": end_time.isoformat(),   "timeZone": "UTC"},
        "attendees": [{"email": candidate_email}],
        "conferenceData": {
            "createRequest": {
                "requestId": f"{candidate_email}-{start_time.timestamp()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
        "reminders": {"useDefault": True},
    }

    created = service.events().insert(
        calendarId="primary",
        body=event,
        conferenceDataVersion=1,
        sendUpdates="all",
    ).execute()

    return created.get("hangoutLink", "")
