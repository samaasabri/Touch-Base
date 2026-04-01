#!/usr/bin/env python3
"""
Google Calendar Authentication Setup Script

Run this once to complete OAuth and generate the local calendar token.
"""

from __future__ import annotations

import sys
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def setup_oauth() -> bool:
    settings = get_settings()
    print("\n=== Google Calendar OAuth Setup ===\n")

    if not settings.credentials_path.exists():
        print(f"Error: {settings.credentials_path} not found!")
        print("\nTo set up Google Calendar integration:")
        print("1. Download your OAuth Desktop credentials JSON")
        print(f"2. Place it at: {settings.credentials_path}")
        return False

    print(f"Found credentials JSON. Starting OAuth flow...")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(settings.credentials_path), SCOPES
        )
        creds = flow.run_local_server(port=0)

        # Persist token for future runs
        settings.calendar_token_path.parent.mkdir(parents=True, exist_ok=True)
        settings.calendar_token_path.write_text(creds.to_json(), encoding="utf-8")

        print(f"\nSaved calendar OAuth token to: {settings.calendar_token_path}")

        # Test the API connection
        print("\nTesting connection to Google Calendar API...")
        service = build("calendar", "v3", credentials=creds)
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get("items", [])

        if calendars:
            print(f"\nSuccess! Found {len(calendars)} calendars:")
            for calendar in calendars:
                print(f"- {calendar['summary']} ({calendar['id']})")
        else:
            print("\nSuccess! Connected to Google Calendar API, but no calendars found.")

        print("\nOAuth setup complete! You can now use the Google Calendar integration.")
        return True
    except Exception as e:
        print(f"\nError during setup: {e}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if setup_oauth() else 1)

