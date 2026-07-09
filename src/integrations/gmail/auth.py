"""
auth.py — Gmail OAuth2 credential management.

Credential loading order (inspired by agents-from-scratch credential chain):
  1. Environment variable GMAIL_TOKEN_JSON (JSON string)
  2. Token file at settings.gmail_token_file
  3. Run interactive OAuth2 flow using settings.gmail_credentials_file

This graceful fallback means the system works in CI/CD (env var),
locally with a saved token file, and on first-run via the OAuth flow.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from src.config.settings import settings
from src.config.constants import GMAIL_SCOPES

logger = logging.getLogger("email_assistant.gmail.auth")

_CREDENTIALS_AVAILABLE = False

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    _CREDENTIALS_AVAILABLE = True
except ImportError:
    logger.warning(
        "Google auth libraries not installed. "
        "Run: pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    )


def get_credentials() -> Optional["Credentials"]:
    """Load and return valid Gmail OAuth2 credentials.

    Returns:
        A refreshed Credentials object, or None if credentials cannot be loaded.
    """
    if not _CREDENTIALS_AVAILABLE:
        logger.warning("Google auth not available — running in mock mode")
        return None

    creds: Optional[Credentials] = None

    # ── Source 1: Environment variable ────────────────────────────────────────
    env_token = os.getenv("GMAIL_TOKEN_JSON")
    if env_token:
        try:
            token_data = json.loads(env_token)
            creds = _credentials_from_dict(token_data)
            logger.info("Loaded Gmail credentials from GMAIL_TOKEN_JSON env var")
        except Exception as e:
            logger.warning("Failed to parse GMAIL_TOKEN_JSON: %s", e)

    # ── Source 2: Token file ───────────────────────────────────────────────────
    if creds is None:
        token_path = settings.gmail_token_file
        if token_path.exists():
            try:
                with open(token_path, "r") as f:
                    token_data = json.load(f)
                creds = _credentials_from_dict(token_data)
                logger.info("Loaded Gmail credentials from %s", token_path)
            except Exception as e:
                logger.warning("Failed to load token file %s: %s", token_path, e)

    # ── Refresh expired credentials ───────────────────────────────────────────
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
            logger.info("Gmail credentials refreshed")
        except Exception as e:
            logger.error("Failed to refresh Gmail credentials: %s", e)
            creds = None

    # ── Source 3: Interactive OAuth flow ──────────────────────────────────────
    if creds is None:
        creds = _run_oauth_flow()

    return creds


def _credentials_from_dict(data: dict) -> "Credentials":
    """Build a Credentials object from a token dict."""
    return Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", GMAIL_SCOPES),
    )


def _run_oauth_flow() -> Optional["Credentials"]:
    """Run the interactive OAuth2 flow."""
    creds_path = settings.gmail_credentials_file
    if not creds_path.exists():
        logger.error(
            "Gmail credentials file not found at %s. "
            "Run 'python tools/generate_token.py' to set up authentication.",
            creds_path,
        )
        return None

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), GMAIL_SCOPES)
        # port=0 lets the OS pick any free port; Desktop ("installed") OAuth
        # clients accept the loopback redirect on any port, so this just works.
        creds = flow.run_local_server(port=settings.gmail_oauth_port)
        _save_token(creds)
        logger.info("OAuth2 flow completed. Token saved.")
        return creds
    except Exception as e:
        logger.error("OAuth2 flow failed: %s", e)
        return None


def _save_token(creds: "Credentials") -> None:
    """Persist refreshed token to file."""
    token_path = settings.gmail_token_file
    token_path.parent.mkdir(parents=True, exist_ok=True)
    with open(token_path, "w") as f:
        json.dump(
            {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes or []),
            },
            f,
            indent=2,
        )
