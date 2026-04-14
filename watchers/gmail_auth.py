"""
Gmail OAuth2 Setup Script — run once to generate credentials.

Usage:
    cd watchers
    python gmail_auth.py

This will open a browser window for Google OAuth consent.
After authorising, a token.json file is saved at watchers/credentials/token.json.
That token is used by gmail_watcher.py and the Gmail MCP server.

Prerequisites:
1. Create a project in Google Cloud Console
2. Enable the Gmail API
3. Create OAuth 2.0 credentials (Desktop app) and download as
   watchers/credentials/gmail_credentials.json
"""

import os
import sys
from pathlib import Path

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",   # read/list emails
    "https://www.googleapis.com/auth/gmail.send",        # send emails
    "https://www.googleapis.com/auth/gmail.compose",     # create drafts
    "https://www.googleapis.com/auth/gmail.modify",      # mark read/labels
]

CREDENTIALS_DIR = Path(__file__).parent / "credentials"
CLIENT_SECRET_FILE = CREDENTIALS_DIR / "gmail_credentials.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError:
        print("ERROR: Missing Google auth libraries.")
        print("Run: uv add google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        sys.exit(1)

    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)

    if not CLIENT_SECRET_FILE.exists():
        print(f"\nERROR: Client secrets file not found at:\n  {CLIENT_SECRET_FILE}")
        print("\nSteps to fix:")
        print("  1. Go to https://console.cloud.google.com/")
        print("  2. Enable the Gmail API for your project")
        print("  3. Create OAuth 2.0 credentials (Desktop app)")
        print("  4. Download the JSON and save as:")
        print(f"     {CLIENT_SECRET_FILE}")
        sys.exit(1)

    creds = None

    # Load existing token if available
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # Refresh or run the full OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing existing token...")
            creds.refresh(Request())
        else:
            print("Starting OAuth2 flow...")
            print("\n" + "="*60)
            print("ACTION REQUIRED: Copy the URL below into your Windows browser:")
            print("="*60 + "\n")
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            creds = flow.run_local_server(host="127.0.0.1", port=8080, open_browser=False, timeout_seconds=300)

        # Save the token for future use
        TOKEN_FILE.write_text(creds.to_json())
        print(f"\n✓ Token saved to: {TOKEN_FILE}")

    # Verify the token works
    from googleapiclient.discovery import build
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email = profile.get("emailAddress", "unknown")
    total = profile.get("messagesTotal", 0)

    print(f"\n✓ Connected as: {email}")
    print(f"  Total messages in account: {total:,}")
    print("\nSetup complete. You can now run gmail_watcher.py")


if __name__ == "__main__":
    main()
