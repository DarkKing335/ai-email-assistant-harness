#!/usr/bin/env python
"""
generate_token.py — One-time Gmail OAuth2 authorisation.

Referenced by docs/guides/gmail-setup.md step 6 and docs/guides/quickstart.md
step 7. Run it once, before you need Gmail; it writes a refresh token to
`credentials/gmail_token.json` and every later run loads it silently.

    python tools/generate_token.py            # authorise (opens a browser)
    python tools/generate_token.py --check    # report status, never prompt
    python tools/generate_token.py --force    # re-authorise, keeping a backup

Why you should run this *before* a demo rather than during one:

`GmailClient.__init__` calls `get_credentials()`, which falls through to
`flow.run_local_server(port=8080)` (auth.py:116) when no token exists. Inside the
desktop GUI that happens on the Tk thread, during `IngestStep`, and it blocks the
event-loop pump — the window freezes until you finish authorising in the browser.
Authorising up front means the GUI only ever loads a token from disk.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Running as `python tools/generate_token.py` puts tools/ on sys.path, not the
# repo root, so `import src...` would fail without this.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.config.constants import GMAIL_SCOPES  # noqa: E402
from src.config.settings import settings  # noqa: E402

EXIT_OK = 0
EXIT_MISSING_LIBS = 1
EXIT_MISSING_CREDENTIALS = 2
EXIT_AUTH_FAILED = 3


def _libraries_installed() -> bool:
    import importlib.util

    def present(name: str) -> bool:
        # find_spec on a submodule imports its parent, and raises if the parent
        # is absent rather than returning None.
        try:
            return importlib.util.find_spec(name) is not None
        except (ImportError, ValueError):
            return False

    return all(present(n) for n in ("googleapiclient", "google_auth_oauthlib", "google.oauth2"))


def _report_status() -> int:
    token = settings.gmail_token_file
    creds = settings.gmail_credentials_file

    print(f"Google libraries : {'installed' if _libraries_installed() else 'NOT INSTALLED'}")
    print(f"Client secrets   : {creds}  {'(found)' if creds.exists() else '(MISSING)'}")
    print(f"OAuth token      : {token}  {'(found)' if token.exists() else '(MISSING)'}")

    if not _libraries_installed():
        print("\nGmail will run in MOCK mode. Install the libraries:")
        print("  pip install google-api-python-client google-auth google-auth-oauthlib")
        return EXIT_MISSING_LIBS
    if not token.exists():
        print("\nNot authorised yet. Run: python tools/generate_token.py")
        return EXIT_MISSING_CREDENTIALS
    print("\nReady. The GUI will load this token without prompting.")
    return EXIT_OK


def _backup_existing_token() -> None:
    token = settings.gmail_token_file
    if not token.exists():
        return
    backup = token.with_suffix(token.suffix + ".bak")
    token.replace(backup)
    print(f"Existing token moved to {backup}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorise this app against Gmail.")
    parser.add_argument("--check", action="store_true", help="Report status and exit.")
    parser.add_argument("--force", action="store_true", help="Re-authorise, backing up any token.")
    args = parser.parse_args()

    if args.check:
        return _report_status()

    if not _libraries_installed():
        print("Google API libraries are not installed. Install them with:\n")
        print("  pip install google-api-python-client google-auth google-auth-oauthlib\n")
        print("Without them the assistant runs in mock mode, which needs no token.")
        return EXIT_MISSING_LIBS

    credentials_file = settings.gmail_credentials_file
    if not credentials_file.exists():
        print(f"Client secrets file not found: {credentials_file}\n")
        print("Create an OAuth 2.0 Desktop client in Google Cloud Console, download the")
        print("JSON, and save it to that path. See docs/guides/gmail-setup.md steps 1-5.")
        return EXIT_MISSING_CREDENTIALS

    if args.force:
        _backup_existing_token()
    elif settings.gmail_token_file.exists():
        print(f"A token already exists at {settings.gmail_token_file}")
        print("Nothing to do. Use --force to re-authorise, or --check to verify it.")
        return EXIT_OK

    print("Requesting these Gmail scopes:")
    for scope in GMAIL_SCOPES:
        note = "  <- only exercised after a human approves a draft" if scope.endswith("send") else ""
        print(f"  {scope}{note}")
    print("\nOpening a browser for authorisation...")

    from src.integrations.gmail.auth import get_credentials

    credentials = get_credentials()
    if credentials is None:
        print("\nAuthorisation failed. No credentials were obtained.")
        return EXIT_AUTH_FAILED

    if not settings.gmail_token_file.exists():
        print(f"\nAuthorisation returned credentials but no token was written to "
              f"{settings.gmail_token_file}.")
        return EXIT_AUTH_FAILED

    print(f"Token saved to {settings.gmail_token_file}")

    from src.integrations.gmail.client import GmailClient

    result = GmailClient().verify()
    if result.get("status") != "ok":
        print(f"Token saved, but the connection check failed: {result.get('status')}")
        return EXIT_AUTH_FAILED

    print(f"Gmail connection verified. Authorised as: {result['email']}")
    print("\nThe GUI's Config tab will now report Gmail status: Connected.")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
